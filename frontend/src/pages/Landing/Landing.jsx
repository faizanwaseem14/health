import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { ContourMotif } from "../../components/ContourMotif/ContourMotif";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { IconBook, IconCheckShield, IconFolder, IconLock } from "./icons";
import styles from "./Landing.module.css";

const VALUE_PROPS = [
  {
    icon: <IconFolder />,
    title: "One place for every report",
    body: "Upload lab reports as photos or PDFs and find them all in one place, instead of scattered folders, emails, and portals.",
  },
  {
    icon: <IconCheckShield />,
    title: "Checked before you see it",
    body: "Every result is checked against the original report before it's shown to you, so what you see always matches what's printed.",
  },
  {
    icon: <IconBook />,
    title: "Explained in plain language",
    body: "Each test comes with a short, plain description of what it measures — never advice, just a clearer picture.",
  },
  {
    icon: <IconLock />,
    title: "Private, and yours alone",
    body: "Your records are kept private and visible only to you and the people you specifically choose to share them with.",
  },
];

export function Landing() {
  return (
    <>
      <section className={styles.hero}>
        <ContourMotif className={styles.heroMotif} />
        <div className={`container ${styles.heroInner}`}>
          <span className={styles.eyebrow}>Private health records, organized</span>
          <h1 className={styles.heroHeadline}>
            Your health records,
            <br />
            finally organized.
          </h1>
          <p className={styles.heroSubhead}>
            HealthVault reads your lab reports, checks every result against the
            original, and explains what each test measures — in plain language,
            kept private, always yours.
          </p>
          <div className={styles.heroActions}>
            <Button as="a" href="#how-it-works" variant="primary">
              See how it works
            </Button>
            <Button as="a" href="#accessibility" variant="secondary">
              Built for every reader
            </Button>
          </div>
        </div>
      </section>

      <section id="how-it-works" className={styles.section}>
        <div className="container">
          <h2 className={styles.sectionHeading}>What HealthVault does</h2>
          <div className={styles.valueGrid}>
            {VALUE_PROPS.map((item) => (
              <Card key={item.title} className={styles.valueCard}>
                <span className={styles.valueIcon}>{item.icon}</span>
                <h3 className={styles.valueTitle}>{item.title}</h3>
                <p className={styles.valueBody}>{item.body}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="accessibility" className={styles.section}>
        <div className="container">
          <Card className={styles.accessibilityCard}>
            <h2 className={styles.sectionHeading}>Designed for every reader</h2>
            <p className={styles.accessibilityBody}>
              HealthVault is built to work for everyone, including the people who
              need it most. Text stays large and easy to read, buttons are big
              enough to tap without precision, and every screen has one clear
              job — no clutter to work around.
            </p>
            <p className={styles.accessibilityBody}>
              Status is never shown with color alone. Every result is always
              marked with a color, an icon, <em>and</em> a word together, like
              this:
            </p>
            <div className={styles.badgeRow}>
              <StatusBadge tone="good" label="Normal" />
              <StatusBadge tone="attention" label="Needs attention" />
              <StatusBadge tone="review" label="Needs review" />
            </div>
            <p className={styles.badgeCaption}>
              Example only — this page doesn't show real results yet.
            </p>
          </Card>
        </div>
      </section>
    </>
  );
}
