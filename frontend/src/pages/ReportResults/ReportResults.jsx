import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { LoadingScreen } from "../../components/LoadingScreen/LoadingScreen";
import { useAuth } from "../../context/AuthContext";
import { describeApiError } from "../../lib/authErrors";
import { ReportPanel } from "./ReportPanel";
import { TestCard } from "./TestCard";
import styles from "./ReportResults.module.css";

const ShieldIcon = () => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
    <path
      d="M12 3.25 19.75 6.5V11.5C19.75 16.2 16.55 20.1 12 21.25C7.45 20.1 4.25 16.2 4.25 11.5V6.5L12 3.25Z"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinejoin="round"
    />
    <path
      d="M8.5 12 10.9 14.4 15.7 9.6"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

/**
 * The calm reminder that belongs at the bottom of every state of this
 * screen: HealthVault describes, it never diagnoses. Rendered in normal
 * flow (not pinned) so it's always reachable by scrolling down, on
 * every version of this screen a user might land on.
 */
function SafetyFooter() {
  return (
    <p className={styles.safetyFooter}>
      <ShieldIcon />
      <span>
        HealthVault tells you what each test measures and what your report says. It never
        diagnoses or gives medical advice — always talk to your doctor about what your results
        mean.
      </span>
    </p>
  );
}

/**
 * A processed report's extracted results, redesigned around the report
 * image itself as the trust anchor: the original page on the left,
 * tappable exactly where each value was found, and a clean results list
 * on the right. Tapping either side opens the same "what is this?"
 * panel (see ExplainPanel.jsx) - deliberately never anything more than
 * what the test measures.
 */
export function ReportResults() {
  const { reportId } = useParams();
  const { authFetch } = useAuth();

  const [filename, setFilename] = useState(null);
  const [results, setResults] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [selectedResultId, setSelectedResultId] = useState(null);
  const [isReportVisible, setIsReportVisible] = useState(true);
  const [isGeneratingExplanations, setIsGeneratingExplanations] = useState(false);
  const [explanationError, setExplanationError] = useState(null);
  const [comingSoonNote, setComingSoonNote] = useState(null);

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

  // Shared by both the report image's tappable regions and the result
  // cards - tapping either selects the same result and, tapping the
  // one that's already selected, closes it.
  function handleSelectResult(resultId) {
    setSelectedResultId((current) => (current === resultId ? null : resultId));
    setExplanationError(null);
  }

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
        <h1 className={styles.heading}>We couldn't load these results</h1>
        <p className={styles.intro}>{loadError}</p>
        <SafetyFooter />
      </div>
    );
  }

  if (results === null) {
    return <LoadingScreen message="Loading your results…" />;
  }

  return (
    <div className={`container ${styles.wrap}`}>
      <div className={styles.header}>
        <div className={styles.headerText}>
          <h1 className={styles.heading}>
            {filename ? `Results for ${filename}` : "Your results"}
          </h1>
          {results.length > 0 && (
            <p className={styles.intro}>
              Tap a value - on the report or in the list below - to see what it measures.
            </p>
          )}
        </div>
        {results.length > 0 && (
          <Button
            type="button"
            variant="secondary"
            size="md"
            onClick={() => setIsReportVisible((visible) => !visible)}
            aria-pressed={!isReportVisible}
          >
            {isReportVisible ? "Hide report" : "Show report"}
          </Button>
        )}
      </div>

      {explanationError && <p className={styles.explanationError}>{explanationError}</p>}

      {results.length === 0 ? (
        <p className={styles.intro}>No test values were extracted from this report.</p>
      ) : (
        <div
          className={`${styles.layout} ${!isReportVisible ? styles.layoutReportHidden : ""}`}
        >
          {isReportVisible && (
            <ReportPanel
              reportId={reportId}
              results={results}
              selectedResultId={selectedResultId}
              onSelectResult={handleSelectResult}
            />
          )}
          <div className={styles.resultsColumn}>
            <h2 className={styles.resultsHeading}>Your results</h2>
            <ul className={styles.list}>
              {results.map((result) => (
                <TestCard
                  key={result.id}
                  result={result}
                  isSelected={selectedResultId === result.id}
                  onSelect={handleSelectResult}
                  onRequestExplanation={handleRequestExplanation}
                  isExplanationLoading={isGeneratingExplanations}
                  onCorrect={handleCorrect}
                />
              ))}
            </ul>
          </div>
        </div>
      )}

      {results.length > 0 && (
        <div className={styles.bottomActions}>
          <Button
            type="button"
            variant="secondary"
            size="lg"
            onClick={() => setComingSoonNote("trends")}
          >
            View trends for this report
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="lg"
            onClick={() => setComingSoonNote("share")}
          >
            Share with doctor
          </Button>
        </div>
      )}
      {comingSoonNote && (
        <p className={styles.comingSoon}>
          {comingSoonNote === "trends"
            ? "Trends across your reports are coming soon."
            : "Sharing reports with your doctor is coming soon."}
        </p>
      )}

      <Link to="/home" className={styles.homeLink}>
        Back to Home
      </Link>

      <SafetyFooter />
    </div>
  );
}
