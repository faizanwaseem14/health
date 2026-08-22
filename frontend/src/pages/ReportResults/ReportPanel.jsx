import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { LoadingScreen } from "../../components/LoadingScreen/LoadingScreen";
import { useAuth } from "../../context/AuthContext";
import { apiFetchBlob } from "../../lib/apiClient";
import { describeApiError } from "../../lib/authErrors";
import styles from "./ReportPanel.module.css";

/**
 * The trust anchor: the report's own page image (rendered server-side
 * at the exact resolution OCR ran against), with a tappable region
 * over every result that has traceable OCR evidence - tapping one
 * selects that result, same as tapping its card in the results list
 * (see ReportResults.jsx, which owns the shared selection state).
 */
export function ReportPanel({ reportId, results, selectedResultId, onSelectResult }) {
  const { authFetch, firebaseUser } = useAuth();

  const [words, setWords] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [activePage, setActivePage] = useState(1);
  const [imageUrl, setImageUrl] = useState(null);
  const [imageError, setImageError] = useState(null);
  const [naturalSize, setNaturalSize] = useState(null);
  const [renderedSize, setRenderedSize] = useState(null);

  useEffect(() => {
    let cancelled = false;
    authFetch(`/reports/${reportId}/ocr-words`)
      .then((response) => {
        if (!cancelled) setWords(response.data);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(describeApiError(error));
      });
    return () => {
      cancelled = true;
    };
  }, [authFetch, reportId]);

  const wordsById = useMemo(() => {
    if (!words) return null;
    return new Map(words.map((word) => [word.id, word]));
  }, [words]);

  // One tappable region per result (the union of its evidence OCR
  // words' boxes), not one per raw word - a card is either tappable on
  // the image as a whole or it isn't.
  const resultRegions = useMemo(() => {
    if (!wordsById) return [];
    return results
      .map((result) => {
        const evidenceWords = result.ocr_word_ids
          .map((id) => wordsById.get(id))
          .filter(Boolean);
        if (evidenceWords.length === 0) return null;

        const points = evidenceWords.flatMap((word) => word.bounding_box);
        const xs = points.map((point) => point[0]);
        const ys = points.map((point) => point[1]);
        return {
          resultId: result.id,
          page: evidenceWords[0].page_number,
          minX: Math.min(...xs),
          minY: Math.min(...ys),
          maxX: Math.max(...xs),
          maxY: Math.max(...ys),
        };
      })
      .filter(Boolean);
  }, [results, wordsById]);

  const pageCount = words
    ? Math.max(1, ...words.map((word) => word.page_number))
    : 1;

  // Jump to whichever page the selected result actually lives on -
  // covers both "selected via its card, evidence is on page 2" and
  // just keeps the two in sync generally.
  useEffect(() => {
    if (!selectedResultId) return;
    const region = resultRegions.find((r) => r.resultId === selectedResultId);
    if (region) setActivePage(region.page);
  }, [selectedResultId, resultRegions]);

  useEffect(() => {
    if (!firebaseUser) return undefined;
    let cancelled = false;
    let objectUrl = null;
    setImageUrl(null);
    setImageError(null);
    setNaturalSize(null);
    setRenderedSize(null);

    firebaseUser
      .getIdToken()
      .then((token) => apiFetchBlob(`/reports/${reportId}/pages/${activePage}`, token))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setImageUrl(objectUrl);
      })
      .catch((error) => {
        if (!cancelled) setImageError(describeApiError(error));
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [reportId, activePage, firebaseUser]);

  function handleImageLoad(event) {
    const img = event.target;
    setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight });
    setRenderedSize({ width: img.clientWidth, height: img.clientHeight });
  }

  if (loadError) {
    return (
      <div className={styles.panel}>
        <p className={styles.error}>{loadError}</p>
      </div>
    );
  }

  if (words === null) {
    return (
      <div className={styles.panel}>
        <LoadingScreen message="Loading your report…" />
      </div>
    );
  }

  const regionsOnPage = resultRegions.filter((region) => region.page === activePage);
  const scaleX = naturalSize && renderedSize ? renderedSize.width / naturalSize.width : null;
  const scaleY = naturalSize && renderedSize ? renderedSize.height / naturalSize.height : null;

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <h2 className={styles.panelHeading}>Your original report</h2>
        <Link to={`/reports/${reportId}/ocr`} className={styles.inspectionLink}>
          Full OCR inspection ↗
        </Link>
      </div>

      {pageCount > 1 && (
        <div className={styles.pageNav}>
          <button
            type="button"
            className={styles.pageButton}
            onClick={() => setActivePage((page) => Math.max(1, page - 1))}
            disabled={activePage === 1}
          >
            ← Previous
          </button>
          <span className={styles.pageLabel}>
            Page {activePage} of {pageCount}
          </span>
          <button
            type="button"
            className={styles.pageButton}
            onClick={() => setActivePage((page) => Math.min(pageCount, page + 1))}
            disabled={activePage === pageCount}
          >
            Next →
          </button>
        </div>
      )}

      <div className={styles.imageFrame}>
        {imageError && <p className={styles.error}>{imageError}</p>}
        {!imageUrl && !imageError && (
          <p className={styles.imageLoading}>Loading page image…</p>
        )}
        {imageUrl && (
          <div className={styles.imageWrap}>
            <img
              src={imageUrl}
              alt={`Page ${activePage} of your original report`}
              className={styles.pageImage}
              onLoad={handleImageLoad}
            />
            {scaleX &&
              regionsOnPage.map((region) => {
                const isSelected = region.resultId === selectedResultId;
                return (
                  <button
                    key={region.resultId}
                    type="button"
                    className={`${styles.region} ${isSelected ? styles.regionSelected : ""}`}
                    style={{
                      left: `${region.minX * scaleX}px`,
                      top: `${region.minY * scaleY}px`,
                      width: `${(region.maxX - region.minX) * scaleX}px`,
                      height: `${(region.maxY - region.minY) * scaleY}px`,
                    }}
                    onClick={() => onSelectResult(region.resultId)}
                    aria-pressed={isSelected}
                    aria-label="Show this value's details"
                  />
                );
              })}
          </div>
        )}
      </div>
    </div>
  );
}
