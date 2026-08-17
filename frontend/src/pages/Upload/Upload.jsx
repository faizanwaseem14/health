import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { useAuth } from "../../context/AuthContext";
import { ApiError } from "../../lib/apiClient";
import { describeApiError } from "../../lib/authErrors";
import { runImageQualityChecks } from "../../lib/imageQualityChecks";
import styles from "./Upload.module.css";

// Keep in sync with backend/app/storage/file_validation.py's
// MAX_UPLOAD_SIZE_BYTES - checking client-side too means an obviously
// too-large file gets a friendly message instantly, instead of only
// after a slow upload attempt that the backend then rejects anyway.
const MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024;

const ACCEPTED_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/heic",
  "image/heif",
  "application/pdf",
]);

function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const DocumentIcon = () => (
  <svg viewBox="0 0 48 48" width="40" height="40" fill="none" aria-hidden="true">
    <path
      d="M12 6h16l8 8v28a2 2 0 0 1-2 2H12a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z"
      stroke="var(--color-brand)"
      strokeWidth="2"
      strokeLinejoin="round"
    />
    <path d="M28 6v8h8" stroke="var(--color-brand)" strokeWidth="2" strokeLinejoin="round" />
    <path d="M16 24h16M16 30h16M16 36h10" stroke="var(--color-brand)" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const CameraIcon = () => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
    <path
      d="M4 8h3l1.5-2.5h7L17 8h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
    />
    <circle cx="12" cy="13.5" r="3.5" stroke="currentColor" strokeWidth="2" />
  </svg>
);

const FolderIcon = () => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
    <path
      d="M3 7a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinejoin="round"
    />
  </svg>
);

/**
 * Upload a lab report: capture a photo or pick a file, preview it,
 * see gentle quality warnings, then confirm to send it to the backend
 * (which kicks off OCR/AI processing - see Processing.jsx).
 */
export function Upload() {
  const { primaryProfile, authFetch } = useAuth();
  const navigate = useNavigate();

  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [qualityWarnings, setQualityWarnings] = useState([]);
  const [isCheckingQuality, setIsCheckingQuality] = useState(false);
  const [pickError, setPickError] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  const cameraInputRef = useRef(null);
  const fileInputRef = useRef(null);

  function resetSelection() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setSelectedFile(null);
    setPreviewUrl(null);
    setQualityWarnings([]);
    setUploadError(null);
    if (cameraInputRef.current) cameraInputRef.current.value = "";
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleFileChosen(event) {
    const file = event.target.files?.[0];
    event.target.value = ""; // lets picking the exact same file again re-fire onChange
    if (!file) return;

    setPickError(null);
    setUploadError(null);

    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
      setPickError("That file is too large — HealthVault accepts files up to 25MB.");
      return;
    }
    if (!ACCEPTED_TYPES.has(file.type)) {
      setPickError(
        "That doesn't look like a photo or PDF HealthVault can read — try a JPEG, PNG, HEIC, or PDF file.",
      );
      return;
    }

    setSelectedFile(file);
    setPreviewUrl(file.type.startsWith("image/") ? URL.createObjectURL(file) : null);
    setQualityWarnings([]);

    setIsCheckingQuality(true);
    try {
      const warnings = await runImageQualityChecks(file);
      setQualityWarnings(warnings);
    } finally {
      setIsCheckingQuality(false);
    }
  }

  async function handleConfirmUpload() {
    if (!selectedFile || !primaryProfile) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const response = await authFetch(`/profiles/${primaryProfile.id}/reports`, {
        method: "POST",
        body: formData,
      });
      navigate(`/reports/${response.data.id}`, { replace: true });
    } catch (error) {
      setUploadError(error instanceof ApiError ? describeApiError(error) : "We couldn't upload that file. Please try again.");
      setIsUploading(false);
    }
  }

  return (
    <div className={`container ${styles.wrap}`}>
      <Card className={styles.card}>
        <h1 className={styles.heading}>Upload a lab report</h1>

        {!selectedFile && (
          <>
            <p className={styles.intro}>
              Take a photo of a printed report, or choose a photo or PDF
              you already have.
            </p>

            <div className={styles.pickButtons}>
              <Button
                type="button"
                variant="primary"
                onClick={() => cameraInputRef.current?.click()}
              >
                <CameraIcon />
                Take a photo
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
              >
                <FolderIcon />
                Choose a file
              </Button>
            </div>

            {pickError && <p className={styles.pickError}>{pickError}</p>}

            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className={styles.hiddenInput}
              onChange={handleFileChosen}
            />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/heic,image/heif,application/pdf"
              className={styles.hiddenInput}
              onChange={handleFileChosen}
            />
          </>
        )}

        {selectedFile && (
          <div className={styles.previewSection}>
            <div className={styles.previewFrame}>
              {previewUrl ? (
                <img src={previewUrl} alt="Preview of the selected report" className={styles.previewImage} />
              ) : (
                <div className={styles.previewDocument}>
                  <DocumentIcon />
                  <div>
                    <p className={styles.previewFileName}>{selectedFile.name}</p>
                    <p className={styles.previewFileSize}>{formatFileSize(selectedFile.size)}</p>
                  </div>
                </div>
              )}
            </div>

            {isCheckingQuality && (
              <p className={styles.checkingQuality}>Checking the photo…</p>
            )}

            {qualityWarnings.length > 0 && (
              <ul className={styles.warningList} aria-label="Photo quality warnings">
                {qualityWarnings.map((warning) => (
                  <li key={warning.id} className={styles.warningItem}>
                    <span className={styles.warningIcon} aria-hidden="true">
                      <svg viewBox="0 0 20 20" width="18" height="18" fill="none">
                        <path
                          d="M10 3.5 17.5 16h-15L10 3.5Z"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinejoin="round"
                        />
                        <path d="M10 8.2v3.6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                        <circle cx="10" cy="14.2" r="1" fill="currentColor" />
                      </svg>
                    </span>
                    <span>{warning.message}</span>
                  </li>
                ))}
              </ul>
            )}

            {uploadError && <p className={styles.uploadError}>{uploadError}</p>}

            <div className={styles.actions}>
              <Button
                type="button"
                variant="primary"
                onClick={handleConfirmUpload}
                disabled={isUploading || isCheckingQuality}
              >
                {isUploading
                  ? "Uploading…"
                  : qualityWarnings.length > 0
                    ? "Upload anyway"
                    : "Confirm & upload"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={resetSelection}
                disabled={isUploading}
              >
                Replace or remove
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
