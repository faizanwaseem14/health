/**
 * Gentle, client-side heuristics that catch the most common reasons a
 * lab report photo comes out unreadable, BEFORE spending a round trip
 * (and the backend's OCR/AI budget) on it: too blurry, too dark/glare,
 * cut off, too small, or sideways.
 *
 * Every check here is a heuristic, not a certainty - there's no ground
 * truth to compare against on the client, just pixels. That's why every
 * result is a soft warning the person can ignore (see Upload.jsx),
 * never something that blocks the upload. If a check can't run at all
 * (a file type the browser can't decode, e.g. some HEIC photos), it
 * fails OPEN - no warning, rather than a false one.
 *
 * Only images are checked; PDFs are skipped entirely (already
 * digital-quality, and there's no cheap way to rasterize one here).
 */

// Longest edge of the downscaled copy we actually analyze pixels on -
// plenty for these checks, and keeps every check fast even on a huge
// original photo.
const ANALYSIS_MAX_DIMENSION = 320;

const MIN_SHORT_EDGE_PX = 700;
const DARK_MEAN_LUMINANCE = 60;
const BRIGHT_MEAN_LUMINANCE = 245;
const GLARE_NEAR_WHITE_FRACTION = 0.35;
const BLUR_VARIANCE_THRESHOLD = 130;
const CUTOFF_BORDER_STDDEV_THRESHOLD = 55;

export const QUALITY_WARNINGS = {
  lowResolution: "This photo is quite small — text may be too blurry to read once processed. A closer, higher-resolution photo works best.",
  tooDark: "This photo looks dark — retake it somewhere brighter for best results?",
  glare: "This photo looks like it has glare or a bright reflection — try tilting the page or moving away from direct light.",
  blurry: "This photo looks blurry — hold steady and retake for best results?",
  cutOff: "Some of the page might be cut off — check all edges and corners are visible.",
  rotated: "This photo might be sideways — rotate it before uploading for best results.",
};

function loadGrayscaleSample(file) {
  return new Promise((resolve, reject) => {
    createImageBitmap(file).then((bitmap) => {
      const scale = Math.min(1, ANALYSIS_MAX_DIMENSION / Math.max(bitmap.width, bitmap.height));
      const width = Math.max(1, Math.round(bitmap.width * scale));
      const height = Math.max(1, Math.round(bitmap.height * scale));

      // Captured before close() below - some browsers stop reporting
      // a bitmap's dimensions once its underlying pixel data is
      // released, which previously made every photo look artificially
      // tiny to checkResolution().
      const originalWidth = bitmap.width;
      const originalHeight = bitmap.height;

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(bitmap, 0, 0, width, height);
      bitmap.close();

      const { data } = ctx.getImageData(0, 0, width, height);
      const gray = new Float32Array(width * height);
      for (let i = 0, p = 0; i < data.length; i += 4, p++) {
        // Standard perceptual luminance weighting.
        gray[p] = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
      }

      resolve({ width, height, gray, originalWidth, originalHeight });
    }, reject);
  });
}

function checkBrightness(gray) {
  let sum = 0;
  let nearWhite = 0;
  for (let i = 0; i < gray.length; i++) {
    sum += gray[i];
    if (gray[i] > 240) nearWhite++;
  }
  const mean = sum / gray.length;

  if (mean < DARK_MEAN_LUMINANCE) return "tooDark";
  if (mean > BRIGHT_MEAN_LUMINANCE && nearWhite / gray.length > GLARE_NEAR_WHITE_FRACTION) {
    return "glare";
  }
  return null;
}

function checkBlur(gray, width, height) {
  // Variance of a simple discrete Laplacian: a sharp photo has lots of
  // strong edges (high variance in the Laplacian response); a blurry
  // one is smoothed out (low variance). A well-known, cheap proxy for
  // focus - not exact, which is exactly why this is a soft warning.
  let sum = 0;
  let sumSq = 0;
  let count = 0;
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const i = y * width + x;
      const lap =
        4 * gray[i] - gray[i - 1] - gray[i + 1] - gray[i - width] - gray[i + width];
      sum += lap;
      sumSq += lap * lap;
      count++;
    }
  }
  if (count === 0) return null;
  const mean = sum / count;
  const variance = sumSq / count - mean * mean;
  return variance < BLUR_VARIANCE_THRESHOLD ? "blurry" : null;
}

function checkCutOff(gray, width, height) {
  // Samples a thin ring right at the edge of the frame. A normal photo
  // has some breathing room (table, background) around the page, which
  // reads as fairly uniform there. If that ring instead has a lot of
  // contrast in it, the page's own content likely runs right up to (or
  // past) the edge of the frame.
  const ring = [];
  for (let x = 0; x < width; x++) {
    ring.push(gray[x], gray[(height - 1) * width + x]);
  }
  for (let y = 0; y < height; y++) {
    ring.push(gray[y * width], gray[y * width + width - 1]);
  }
  const mean = ring.reduce((a, b) => a + b, 0) / ring.length;
  const variance = ring.reduce((a, b) => a + (b - mean) * (b - mean), 0) / ring.length;
  return Math.sqrt(variance) > CUTOFF_BORDER_STDDEV_THRESHOLD ? "cutOff" : null;
}

function checkResolution(originalWidth, originalHeight) {
  return Math.min(originalWidth, originalHeight) < MIN_SHORT_EDGE_PX ? "lowResolution" : null;
}

/**
 * Reads a JPEG's EXIF Orientation tag directly out of its bytes - the
 * one genuinely reliable "is this sideways" signal available without
 * actually understanding the image content. Orientation values 5-8 all
 * mean a 90-or-270-degree rotation is baked into how the camera saved
 * it. Only JPEGs carry EXIF this way; other formats are skipped.
 */
async function checkRotation(file) {
  if (file.type !== "image/jpeg") return null;

  // EXIF lives in the first segment or two of the file - no need to
  // read the whole (potentially huge) original photo for this.
  const head = await file.slice(0, 65536).arrayBuffer();
  const view = new DataView(head);
  if (view.getUint16(0) !== 0xffd8) return null; // not a JPEG after all

  let offset = 2;
  while (offset + 4 <= view.byteLength) {
    const marker = view.getUint16(offset);
    if (marker === 0xffe1) {
      return readOrientationFromExifSegment(view, offset + 4);
    }
    if ((marker & 0xff00) !== 0xff00) break; // not a marker - bail out
    const segmentLength = view.getUint16(offset + 2);
    offset += 2 + segmentLength;
  }
  return null;
}

function readOrientationFromExifSegment(view, exifStart) {
  // "Exif\0\0" header, then a TIFF header: 2 bytes byte-order ("II" or
  // "MM"), then IFD0's offset (relative to the TIFF header).
  if (view.getUint32(exifStart) !== 0x45786966) return null; // "Exif"
  const tiffStart = exifStart + 6;
  const little = view.getUint16(tiffStart) === 0x4949; // "II"
  const ifdOffset = view.getUint32(tiffStart + 4, little);

  const entryCount = view.getUint16(tiffStart + ifdOffset, little);
  for (let i = 0; i < entryCount; i++) {
    const entryStart = tiffStart + ifdOffset + 2 + i * 12;
    const tag = view.getUint16(entryStart, little);
    if (tag === 0x0112) {
      const orientation = view.getUint16(entryStart + 8, little);
      return orientation >= 5 && orientation <= 8 ? "rotated" : null;
    }
  }
  return null;
}

/**
 * Runs every check and returns the warnings that fired, each as
 * `{ id, message }` (id matches a key in QUALITY_WARNINGS - handy for
 * tests/analytics later; message is what to actually show).
 *
 * Never throws: a file the browser can't decode (unsupported HEIC
 * variant, corrupt file) just means no warnings, not a crash - the
 * upload itself will still validate the file for real server-side.
 */
export async function runImageQualityChecks(file) {
  if (!file.type.startsWith("image/")) return [];

  const warningIds = new Set();

  try {
    const { width, height, gray, originalWidth, originalHeight } =
      await loadGrayscaleSample(file);

    const resolutionWarning = checkResolution(originalWidth, originalHeight);
    if (resolutionWarning) warningIds.add(resolutionWarning);

    const brightnessWarning = checkBrightness(gray);
    if (brightnessWarning) warningIds.add(brightnessWarning);

    const blurWarning = checkBlur(gray, width, height);
    if (blurWarning) warningIds.add(blurWarning);

    const cutOffWarning = checkCutOff(gray, width, height);
    if (cutOffWarning) warningIds.add(cutOffWarning);
  } catch {
    // Fails open - see the module doc comment.
  }

  try {
    const rotationWarning = await checkRotation(file);
    if (rotationWarning) warningIds.add(rotationWarning);
  } catch {
    // Same - a malformed EXIF segment just means we skip that one check.
  }

  return [...warningIds].map((id) => ({ id, message: QUALITY_WARNINGS[id] }));
}
