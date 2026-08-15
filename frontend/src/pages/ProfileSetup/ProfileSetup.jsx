import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Button } from "../../components/Button/Button";
import { Card } from "../../components/Card/Card";
import { Input } from "../../components/Input/Input";
import { useAuth } from "../../context/AuthContext";
import { describeApiError } from "../../lib/authErrors";
import styles from "./ProfileSetup.module.css";

const SEX_OPTIONS = ["Female", "Male", "Prefer not to say"];

export function ProfileSetup() {
  const { hasProfile, authFetch, refreshProfiles } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [sex, setSex] = useState("");
  const [nameError, setNameError] = useState(null);
  const [submitError, setSubmitError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  // A returning visitor who already finished this shouldn't see it
  // again if they navigate back here directly.
  if (hasProfile) {
    return <Navigate to="/home" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setNameError(null);
    setSubmitError(null);

    if (!fullName.trim()) {
      setNameError("Enter your name.");
      return;
    }

    setIsSaving(true);
    try {
      await authFetch("/profiles", {
        method: "POST",
        body: {
          full_name: fullName.trim(),
          date_of_birth: dateOfBirth || null,
          sex: sex || null,
        },
      });
      await refreshProfiles();
      navigate("/home", { replace: true });
    } catch (error) {
      setSubmitError(describeApiError(error));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className={`container ${styles.wrap}`}>
      <Card className={styles.card}>
        <h1 className={styles.heading}>Set up your profile</h1>
        <p className={styles.intro}>
          This is who your health records belong to. You can add profiles
          for family members you manage later.
        </p>

        <form onSubmit={handleSubmit} className={styles.form} noValidate>
          <Input
            label="Full name"
            type="text"
            autoComplete="name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            error={nameError}
            disabled={isSaving}
          />

          <Input
            label="Date of birth"
            hint="Optional"
            type="date"
            autoComplete="bday"
            value={dateOfBirth}
            onChange={(event) => setDateOfBirth(event.target.value)}
            disabled={isSaving}
          />

          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>
              Sex <span className={styles.optional}>(optional)</span>
            </legend>
            <div className={styles.radioGroup}>
              {SEX_OPTIONS.map((option) => (
                <label key={option} className={styles.radioOption}>
                  <input
                    type="radio"
                    name="sex"
                    value={option}
                    checked={sex === option}
                    onChange={() => setSex(option)}
                    disabled={isSaving}
                  />
                  <span>{option}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {submitError && <p className={styles.submitError}>{submitError}</p>}

          <Button type="submit" variant="primary" disabled={isSaving}>
            {isSaving ? "Saving…" : "Continue"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
