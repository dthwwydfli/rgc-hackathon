export function WanderingEyes() {
  return (
    <span className="swimlanes-wandering-eyes" role="status" aria-live="polite">
      <span className="swimlanes-wandering-eyes-pair" aria-hidden="true">
        <span className="swimlanes-wandering-eye" />
        <span className="swimlanes-wandering-eye" />
      </span>
      <span className="swimlanes-visually-hidden">Loading</span>
    </span>
  );
}
