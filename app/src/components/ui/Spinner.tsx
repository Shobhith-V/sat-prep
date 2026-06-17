export function Spinner() {
  return <div className="spinner" role="status" aria-label="Loading" />;
}

export function FullPageSpinner() {
  return (
    <div className="spinner-center">
      <Spinner />
    </div>
  );
}
