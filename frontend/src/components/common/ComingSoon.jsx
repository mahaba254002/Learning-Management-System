export default function ComingSoon({ title }) {
  return (
    <div>
      <h1 style={{ fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", marginBottom: "0.5rem" }}>
        {title}
      </h1>
      <p style={{ color: "var(--color-ink-soft)" }}>
        This section is coming soon.
      </p>
    </div>
  );
}