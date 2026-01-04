interface DepartmentFilterProps {
  departments: string[];
  value: string;
  onChange: (value: string) => void;
  isLoading?: boolean;
}

export function DepartmentFilter({
  departments,
  value,
  onChange,
  isLoading = false,
}: DepartmentFilterProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={isLoading}
      className="block w-full px-4 py-2 border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <option value="">All Departments</option>
      {departments.map((dept) => (
        <option key={dept} value={dept}>
          {dept}
        </option>
      ))}
    </select>
  );
}

export default DepartmentFilter;
