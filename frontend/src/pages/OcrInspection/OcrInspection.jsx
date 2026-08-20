import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { LoadingScreen } from "../../components/LoadingScreen/LoadingScreen";
import { useAuth } from "../../context/AuthContext";
import { apiFetchBlob } from "../../lib/apiClient";
import { describeApiError } from "../../lib/authErrors";
import styles from "./OcrInspection.module.css";

/**
 * Lets someone compare an extracted value against exactly where
 * HealthVault read it from on the original report: the report's own
 * page image, with a box drawn around every word OCR detected -
 * highlighted ones (arriving here via "View in original report" on a
 * specific result - see ResultRow.jsx) are that result's own evidence.
 */
export function OcrInspection() {
  const { reportId } = useParams();
  const location = useLocation();
  const { authFetch, firebaseUser } = useAuth();

  // Only meaningful on the very first render this screen sees after
  // navigating here from a specific result - a page refresh loses
  // location.state, and that's fine: everything just shows unhighlighted.
  const highlightWordIds = useMemo(
    () => new Set(location.state?.highlightWordIds ?? []),
    [location.state],
  );

  const [words, setWords] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [activePage, setActivePage] = useState(1);
  const [imageUrl, setImageUrl] = useState(null);
  const [imageError, setImageError] = useState(null);
  const [renderedSize, setRenderedSize] = useState(null);
  const [naturalSize, setNaturalSize] = useState(null);
  const imgRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    authFetch(`/reports/${reportId}/ocr-words`)
      .then((response) => {
        if (cancelled) return;
        setWords(response.data);
        if (highlightWordIds.size > 0) {
          const firstMatch = response.data.find((word) => highlightWordIds.has(word.id));
          if (firstMatch) setActivePage(firstMatch.page_number);
        }
      })
      .catch((error) => {
        if (!cancelled) setLoadError(describeApiError(error));
      });
    return () => {
      cancelled = true;
    };
    // highlightWordIds is derived from location.state, which doesn't
    // change after arriving here - only reacting to reportId/authFetch
    // avoids re-fetching every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authFetch, reportId]);

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
      <div className={`container ${styles.wrap}`}>
        <Card className={styles.card}>
          <h1 className={styles.heading}>We couldn't load the original report</h1>
          <p className={styles.intro}>{loadError}</p>
          <Link to={`/reports/${reportId}/results`} className={styles.backLink}>
            Back to results
          </Link>
        </Card>
      </div>
    );
  }

  if (words === null) {
    return <LoadingScreen message="Loading the original report…" />;
  }

  const pageCount = Math.max(1, ...words.map((word) => word.page_number));
  const wordsOnPage = words.filter((word) => word.page_number === activePage);
  const scaleX = naturalSize && renderedSize ? renderedSize.width / naturalSize.width : null;
  const scaleY = naturalSize && renderedSize ? renderedSize.height / naturalSize.height : null;

  return (
    <div className={`container ${styles.wrap}`}>
      <Card className={styles.card}>
        <h1 className={styles.heading}>Compare against the original</h1>
        <p className={styles.intro}>
          {highlightWordIds.size > 0
            ? "The highlighted text below is exactly where this value was read from."
            : "Every word HealthVault could read off this page, and exactly where it found it."}
        </p>

        {pageCount > 1 && (
          <div className={styles.pageNav}>
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => setActivePage((page) => Math.max(1, page - 1))}
              disabled={activePage === 1}
            >
              Previous page
            </Button>
            <span className={styles.pageLabel}>
              Page {activePage} of {pageCount}
            </span>
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => setActivePage((page) => Math.min(pageCount, page + 1))}
              disabled={activePage === pageCount}
            >
              Next page
            </Button>
          </div>
        )}

        <div className={styles.imageFrame}>
          {imageError && <p className={styles.imageError}>{imageError}</p>}
          {!imageUrl && !imageError && (
            <p className={styles.imageLoading}>Loading page image…</p>
          )}
          {imageUrl && (
            <div className={styles.imageWrap}>
              <img
                ref={imgRef}
                src={imageUrl}
                alt={`Page ${activePage} of the original report`}
                className={styles.pageImage}
                onLoad={handleImageLoad}
              />
              {scaleX &&
                wordsOnPage.map((word) => {
                  const xs = word.bounding_box.map((point) => point[0]);
                  const ys = word.bounding_box.map((point) => point[1]);
                  const minX = Math.min(...xs);
                  const minY = Math.min(...ys);
                  const maxX = Math.max(...xs);
                  const maxY = Math.max(...ys);
                  const isHighlighted = highlightWordIds.has(word.id);
                  return (
                    <span
                      key={word.id}
                      className={`${styles.wordBox} ${isHighlighted ? styles.wordBoxHighlighted : ""}`}
                      style={{
                        left: `${minX * scaleX}px`,
                        top: `${minY * scaleY}px`,
                        width: `${(maxX - minX) * scaleX}px`,
                        height: `${(maxY - minY) * scaleY}px`,
                      }}
                      title={word.text}
                    />
                  );
                })}
            </div>
          )}
        </div>

        <details className={styles.transcript}>
          <summary>Read the detected text instead</summary>
          <p className={styles.transcriptText}>
            {wordsOnPage.map((word) => word.text).join(" ") || "No text detected on this page."}
          </p>
        </details>

        <Link to={`/reports/${reportId}/results`} className={styles.backLink}>
          Back to results
        </Link>
      </Card>
    </div>
  );
}
