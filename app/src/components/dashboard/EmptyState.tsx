export function EmptyState({
  icon = '📊',
  title,
  message,
}: {
  icon?: string;
  title: string;
  message: string;
}) {
  return (
    <div className="dash-empty">
      <div className="dash-empty-icon" aria-hidden>{icon}</div>
      <div className="dash-empty-title">{title}</div>
      <p className="dash-empty-msg">{message}</p>
    </div>
  );
}
