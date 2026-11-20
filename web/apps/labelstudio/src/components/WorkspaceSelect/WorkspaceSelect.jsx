import { useEffect, useMemo, useState } from "react";
import { Select } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";

const NO_WORKSPACE_VALUE = "none";

/**
 * Workspace picker. Offers "No workspace" plus the workspaces the user can manage.
 * `onChange(idOrNull, title)`. `extraOption` ({id, title}) is added when missing, so the current workspace of a project is always displayed.
 */
export const WorkspaceSelect = ({ value, onChange, disabled, extraOption }) => {
  const api = useAPI();
  const [workspaces, setWorkspaces] = useState([]);

  useEffect(() => {
    let cancelled = false;

    const fetchWorkspaces = async () => {
      const result = await api.callApi("workspaces", { suppressError: true });
      if (cancelled || result?.error) return;
      setWorkspaces(Array.isArray(result) ? result : []);
    };

    fetchWorkspaces();
    return () => {
      cancelled = true;
    };
  }, [api]);

  const options = useMemo(() => {
    const manageableOptions = workspaces
      .filter((workspace) => workspace.can_manage)
      .map((workspace) => ({ value: String(workspace.id), label: workspace.title }));

    if (extraOption && !manageableOptions.some((option) => option.value === String(extraOption.id))) {
      manageableOptions.push({ value: String(extraOption.id), label: extraOption.title });
    }
    return [{ value: NO_WORKSPACE_VALUE, label: "No workspace" }, ...manageableOptions];
  }, [workspaces, extraOption]);

  return (
    <Select
      options={options}
      value={value === null || value === undefined ? NO_WORKSPACE_VALUE : String(value)}
      onChange={(selectedValue) => {
        if (selectedValue === NO_WORKSPACE_VALUE) {
          onChange(null, null);
          return;
        }
        const selectedOption = options.find((option) => option.value === selectedValue);
        onChange(Number(selectedValue), selectedOption?.label);
      }}
      disabled={disabled}
      testId="workspace-select"
    />
  );
};
