import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "../../components/Card/Card";
import { LoadingScreen } from "../../components/LoadingScreen/LoadingScreen";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import { describeApiError } from "../../lib/authErrors";
import { ResultRow } from "./ResultRow";
import styles from "./ReportResults.module.css";

/**
 * A processed report's extracted results: what each test measured,
 * whether it's in the normal range, and how much to trust the reading
 * - plus, per result, an on-demand plain-language explanation and a
 * way to correct a misread value (see ResultRow.jsx for that detail).
 */
export function ReportResults() {
  const { reportId } = useParams();
  const { authFetch } = useAuth();

  const [filename, setFilename] = useState(null);
  const [results, setResults] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [expandedResultId, setExpandedResultId] = useState(null);
  const [isGeneratingExplanations, setIsGeneratingExplanations] = useState(false);
  const [explanationError, setExplanationError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([authFetch(`/reports/${reportId}`), authFetch(`/reports/${reportId}/results`)])
      .then(([reportResponse, resultsResponse]) => {
        if (cancelled) return;
        setFilename(reportResponse.data.original_filename);
        setResults(resultsResponse.data);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(describeApiError(error));
      });

    return () => {
      cancelled = true;
    };
  }, [authFetch, reportId]);

  function handleToggleExpand(resultId) {
    setExpandedResultId((current) => (current === resultId ? null : resultId));
    setExplanationError(null);
  }

  // Generates explanations for the WHOLE report at once (the backend
  // caches one Claude call per distinct test name, not per result) -
  // only ever called the first time someone taps a result that doesn't
  // already have one. Every other result's explanation comes along in
  // the same response, so tapping a second, third, ... result never
  // triggers another call.
  const handleRequestExplanation = useCallback(
    async (resultId) => {
      const target = results?.find((result) => result.id === resultId);
      if (target?.explanation) return;

      setIsGeneratingExplanations(true);
      setExplanationError(null);
      try {
        const response = await authFetch(`/reports/${reportId}/explanations`, {
          method: "POST",
        });
        const explanationsById = response.data;
        setResults((current) =>
          current.map((result) => ({
            ...result,
            explanation: explanationsById[result.id] ?? result.explanation,
          })),
        );
      } catch (error) {
        setExplanationError(describeApiError(error));
      } finally {
        setIsGeneratingExplanations(false);
      }
    },
    [authFetch, reportId, results],
  );

  const handleCorrect = useCallback(
    async (resultId, payload) => {
      const response = await authFetch(`/results/${resultId}/corrections`, {
        method: "POST",
        body: payload,
      });
      setResults((current) =>
        current.map((result) => (result.id === resultId ? response.data : result)),
      );
    },
    [authFetch],
  );

  if (loadError) {
    return (
      <div className={`container ${styles.wrap}`}>
        <Card className={styles.card}>
          <h1 className={styles.heading}>We couldn't load these results</h1>
          <p className={styles.intro}>{loadError}</p>
        </Card>
      </div>
    );
  }

  if (results === null) {
    return <LoadingScreen message="Loading your results…" />;
  }

  return (
    <div className={`container ${styles.wrap}`}>
      <Card className={styles.card}>
        <StatusBadge tone="good" label="Processed" />
        <h1 className={styles.heading}>
          {filename ? `Results for ${filename}` : "Your results"}
        </h1>

        {results.length === 0 ? (
          <p className={styles.intro}>
            No test values were extracted from this report.
          </p>
        ) : (
          <>
            <p className={styles.intro}>
              Tap a result to see what it measures, its full history, or
              to fix a value if something was misread.
            </p>
            {explanationError && (
              <p className={styles.explanationError}>{explanationError}</p>
            )}
            <ul className={styles.list}>
              {results.map((result) => (
                <ResultRow
                  key={result.id}
                  result={result}
                  reportId={reportId}
                  isExpanded={expandedResultId === result.id}
                  onToggleExpand={() => handleToggleExpand(result.id)}
                  onRequestExplanation={handleRequestExplanation}
                  isExplanationLoading={isGeneratingExplanations}
                  onCorrect={handleCorrect}
                />
              ))}
            </ul>
          </>
        )}

        <Link to="/home" className={styles.homeLink}>
          Back to Home
        </Link>
      </Card>
    </div>
  );
}
