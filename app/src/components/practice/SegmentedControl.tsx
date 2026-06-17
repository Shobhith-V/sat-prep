interface Option<T extends string> {
  value: T;
  label: string;
}

/** Accessible segmented button group used for Section and Difficulty. */
export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="ps-field">
      <span className="ps-label">{label}</span>
      <div className="ps-segmented" role="group" aria-label={label}>
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`ps-segment${value === opt.value ? ' is-active' : ''}`}
            aria-pressed={value === opt.value}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
