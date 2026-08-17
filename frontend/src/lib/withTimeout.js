/**
 * Wraps a promise so it can never hang a screen forever: if it hasn't
 * settled within `timeoutMs`, rejects with a TimeoutError instead of
 * leaving the caller waiting indefinitely. Used around calls into
 * Firebase's phone-auth SDK, which depends on a third-party script
 * (Google's reCAPTCHA) that can stall with no thrown error if it's
 * blocked or slow to load.
 */
export class TimeoutError extends Error {
  constructor(message = "This is taking longer than expected.") {
    super(message);
    this.name = "TimeoutError";
  }
}

export function withTimeout(promise, timeoutMs) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new TimeoutError()), timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}
