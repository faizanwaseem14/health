import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { LoadingScreen } from "../../components/LoadingScreen/LoadingScreen";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useAuth } from "../../context/AuthContext";
import { describeApiError } from "../../lib/authErrors";
import { describeResultFlag } from "../../lib/resultStatus";
import { describeLatestValueNote } from "../../lib/trendNotes";
import { TrendChart } from "./TrendChart";
import styles from "./Trends.module.css";

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

function SafetyFooter() {
  return (
    <p className={styles.safetyFooter}>
      <ShieldIcon />
      <span>
        Trends show your own reported values over time against your reports' printed
        ranges. HealthVault never diagnoses or gives medical advice — always talk to your
        doctor about what your results mean.
      </span>
    </p>
  );
}

function formatValue(value, unit) {
  return unit ? `${value} ${unit}` : value;
}

/**
 * Every test extracted from this report, as a compact grid: name,
 * value, status. A tile for a test that's resolved to the catalog
 * (has a trend) is a button that selects it below; everything else is
 * shown but not clickable - honest about what "every test" actually
 * covers here, per the trend validity guard (see
 * app/trends/service.py) - an unresolved raw test name can't be safely
 * grouped with anything from another report.
 */
function OverviewGrid({ results, trendAliasIds, selectedAliasId, onSelect }) {
  return (
    <div className={styles.grid}>
      {results.map((result) => {
        const badge = describeResultFlag(result.flag);
        const isTrendable = result.test_alias_id && trendAliasIds.has(result.test_alias_id);
        const isSelected = isTrendable && result.test_alias_id === selectedAliasId;
        const tileClass = [
          styles.tile,
          badge?.tone === "attention" || badge?.tone === "low" ? styles.tileOutOfRange : "",
          isSelected ? styles.tileSelected : "",
        ]
          .filter(Boolean)
          .join(" ");

        const content = (
          <>
            <span className={styles.tileName}>
              {result.canonical_test_name || result.raw_test_name}
            </span>
            <span className={styles.tileValue}>{formatValue(result.value, result.unit)}</span>
            {badge && <StatusBadge tone={badge.tone} label={badge.label} className={styles.tileBadge} />}
            {!isTrendable && <span className={styles.tileNote}>Not tracked over time yet</span>}
          </>
        );

        return isTrendable ? (
          <button
            key={result.id}
            type="button"
            className={tileClass}
            onClick={() => onSelect(result.test_alias_id)}
            aria-pressed={isSelected}
          >
            {content}
          </button>
        ) : (
          <div key={result.id} className={tileClass}>
            {content}
          </div>
        );
      })}
    </div>
  );
}

/**
 * The trends screen: a whole-report overview grid on top, and below it
 * one test's full history - either a chart (>=2 comparable points), a
 * friendly "upload another report" state (exactly 1), or a friendly
 * "can't be tracked yet" state (not resolved to the catalog at all).
 * Reachable from "View trends for this report" and a per-test "See
 * trend over time" on the results screen.
 */
export function Trends() {
  const { reportId } = useParams();
  const { authFetch } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [reportName, setReportName] = useState(null);
  const [results, setResults] = useState(null);
  const [trends, setTrends] = useState(null);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      authFetch(`/reports/${reportId}`),
      authFetch(`/reports/${reportId}/results`),
      authFetch(`/reports/${reportId}/trends`),
    ])
      .then(([reportResponse, resultsResponse, trendsResponse]) => {
        if (cancelled) return;
        setReportName(reportResponse.data.display_name || reportResponse.data.original_filename);
        setResults(resultsResponse.data);
        setTrends(trendsResponse.data.tests);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(describeApiError(error));
      });

    return () => {
      cancelled = true;
    };
  }, [authFetch, reportId]);

  const trendByAliasId = useMemo(() => {
    if (!trends) return new Map();
    return new Map(trends.map((trend) => [trend.test_alias_id, trend]));
  }, [trends]);

  const selectedAliasId = searchParams.get("test");

  // Default to the first trend-eligible test once trends load, if
  // nothing was already picked via a direct link.
  useEffect(() => {
    if (!trends || selectedAliasId) return;
    if (trends.length > 0) {
      setSearchParams({ test: trends[0].test_alias_id }, { replace: true });
    }
  }, [trends, selectedAliasId, setSearchParams]);

  function selectTest(aliasId) {
    setSearchParams({ test: aliasId });
  }

  if (loadError) {
    return (
      <div className={`container ${styles.wrap}`}>
        <h1 className={styles.heading}>We couldn't load trends</h1>
        <p className={styles.intro}>{loadError}</p>
        <SafetyFooter />
      </div>
    );
  }

  if (results === null || trends === null) {
    return <LoadingScreen message="Loading trends…" />;
  }

  const selectedTrend = selectedAliasId ? trendByAliasId.get(selectedAliasId) : null;
  const trendAliasIds = new Set(trends.map((trend) => trend.test_alias_id));

  return (
    <div className={`container ${styles.wrap}`}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.heading}>Trends for {reportName}</h1>
          <p className={styles.intro}>
            How each test has changed across your reports over time.
          </p>
        </div>
        <Link to={`/reports/${reportId}/results`} className={styles.backLink}>
          ← Back to results
        </Link>
      </div>

      {results.length === 0 ? (
        <p className={styles.intro}>This report has no extracted results to show trends for.</p>
      ) : (
        <>
          <section className={styles.section}>
            <h2 className={styles.sectionHeading}>Every test in this report</h2>
            <OverviewGrid
              results={results}
              trendAliasIds={trendAliasIds}
              selectedAliasId={selectedAliasId}
              onSelect={selectTest}
            />
          </section>

          <section className={styles.section}>
            <h2 className={styles.sectionHeading}>Test history</h2>

            {trends.length === 0 ? (
              <p className={styles.intro}>
                None of this report's tests are matched to HealthVault's test catalog yet, so
                there's nothing to safely compare over time.
              </p>
            ) : (
              <>
                <div className={styles.chips} role="tablist" aria-label="Choose a test">
                  {trends.map((trend) => (
                    <button
                      key={trend.test_alias_id}
                      type="button"
                      role="tab"
                      aria-selected={trend.test_alias_id === selectedAliasId}
                      className={`${styles.chip} ${
                        trend.test_alias_id === selectedAliasId ? styles.chipSelected : ""
                      }`}
                      onClick={() => selectTest(trend.test_alias_id)}
                    >
                      {trend.canonical_name}
                    </button>
                  ))}
                </div>

                {selectedTrend && <TestTrendPanel trend={selectedTrend} />}
              </>
            )}
          </section>
        </>
      )}

      <SafetyFooter />
    </div>
  );
}

function TestTrendPanel({ trend }) {
  const latestBadge = describeResultFlag(trend.latest.flag);
  const note = describeLatestValueNote(trend.canonical_name, trend.latest.flag);

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <div>
          <p className={styles.latestLabel}>Latest value</p>
          <p className={styles.latestValue}>
            {formatValue(trend.latest.value, trend.latest.unit)}
          </p>
        </div>
        {latestBadge && <StatusBadge tone={latestBadge.tone} label={latestBadge.label} />}
      </div>

      {trend.latest.reference_range_text && (
        <p className={styles.rangeNote}>
          Reference range (latest report): {trend.latest.reference_range_text}
          {trend.latest.unit ? ` ${trend.latest.unit}` : ""}
        </p>
      )}

      {note && <p className={styles.factualNote}>{note}</p>}

      {trend.has_trend ? (
        <TrendChart
          points={trend.points}
          referenceRangeText={trend.latest.reference_range_text}
        />
      ) : (
        <p className={styles.singlePointNote}>
          Upload another report to see a trend over time for this test.
        </p>
      )}

      {trend.excluded_points.length > 0 && (
        <p className={styles.excludedNote}>
          {trend.excluded_points.length} earlier result
          {trend.excluded_points.length === 1 ? "" : "s"} couldn't be safely compared (a
          different, non-convertible unit or a non-numeric value) and{" "}
          {trend.excluded_points.length === 1 ? "isn't" : "aren't"} shown on the chart above.
        </p>
      )}
    </div>
  );
}
