import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Select, Typography, useToast } from "@humansignal/ui";
import Input from "../Form/Elements/Input/Input";
import { confirm } from "../Modal/Modal";
import { Spinner } from "../Spinner/Spinner";
import { useAPI } from "../../providers/ApiProvider";

export const ROLE_OPTIONS = [
  { value: "manager", label: "Manager" },
  { value: "reviewer", label: "Reviewer" },
  { value: "annotator", label: "Annotator" },
];

const getRoleLabel = (role) => ROLE_OPTIONS.find((option) => option.value === role)?.label ?? role;

const getDisplayName = (member) => `${member.first_name ?? ""} ${member.last_name ?? ""}`.trim() || member.email;

const getFirstErrorMessage = (result) => {
  const validationErrors = result?.response?.validation_errors;
  const firstFieldMessage = validationErrors?.email?.[0] ?? validationErrors?.role?.[0];
  return firstFieldMessage ?? validationErrors?.non_field_errors?.[0] ?? result?.response?.detail ?? "Request failed";
};

/**
 * Member management (invite by email, role change, removal) for a project or a workspace.
 * Rows with `role === null` and a `workspace_role` are inherited from the workspace and read-only.
 */
export const RoleMembers = ({
  listEndpoint,
  assignEndpoint,
  revokeEndpoint,
  pk,
  scopeLabel,
  testIdPrefix = "members",
  onForbiddenChange,
}) => {
  const api = useAPI();
  const toast = useToast();

  const [members, setMembers] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [forbidden, setForbidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("annotator");
  const [formError, setFormError] = useState(null);

  useEffect(() => {
    onForbiddenChange?.(forbidden);
  }, [forbidden, onForbiddenChange]);

  const fetchMembers = useCallback(async () => {
    if (!pk) return;
    const result = await api.callApi(listEndpoint, { params: { pk }, suppressError: true });

    if (result?.error) {
      if (result.$meta?.status === 403) {
        setForbidden(true);
      } else {
        setLoadError(result.response?.detail ?? "Failed to load members");
      }
      return;
    }
    setForbidden(false);
    setLoadError(null);
    setMembers(Array.isArray(result) ? result : []);
  }, [api, listEndpoint, pk]);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  const runRequest = async (request) => {
    setBusy(true);
    try {
      return await request();
    } finally {
      setBusy(false);
    }
  };

  const addMember = () =>
    runRequest(async () => {
      setFormError(null);
      const result = await api.callApi(assignEndpoint, {
        params: { pk },
        body: { email: newEmail.trim(), role: newRole },
        suppressError: true,
      });

      if (result?.error) {
        setFormError(getFirstErrorMessage(result));
        return;
      }
      setNewEmail("");
      toast.show({ message: "Member added" });
      await fetchMembers();
    });

  const changeRole = (member, role) =>
    runRequest(async () => {
      const result = await api.callApi(assignEndpoint, {
        params: { pk },
        body: { user: member.user, role },
        suppressError: true,
      });

      if (result?.error) {
        toast.show({ message: getFirstErrorMessage(result), type: "error" });
      }
      await fetchMembers();
    });

  const removeMember = (member) =>
    runRequest(async () => {
      const result = await api.callApi(revokeEndpoint, {
        params: { pk, userPk: member.user },
        suppressError: true,
      });

      if (result?.error) {
        toast.show({ message: getFirstErrorMessage(result), type: "error" });
      }
      await fetchMembers();
    });

  const confirmRemoval = (member) => {
    confirm({
      title: "Remove member",
      body: `Remove ${getDisplayName(member)} from this ${scopeLabel}?`,
      okText: "Remove",
      buttonLook: "negative",
      onOk: () => removeMember(member),
    });
  };

  if (forbidden) {
    return <Typography variant="body">Only {scopeLabel} managers can manage members.</Typography>;
  }

  if (loadError) {
    return (
      <Typography variant="body" className="text-negative-content" data-testid={`${testIdPrefix}-load-error`}>
        Could not load members: {loadError}
      </Typography>
    );
  }

  if (!members) {
    return (
      <div style={{ display: "flex", justifyContent: "center", marginTop: 32 }}>
        <Spinner size={32} />
      </div>
    );
  }

  return (
    <>
      <form
        className="flex gap-base items-end mb-base"
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy && newEmail.trim()) addMember();
        }}
      >
        <div style={{ flex: 1 }}>
          <Input
            type="email"
            placeholder="Email address"
            value={newEmail}
            onChange={(event) => setNewEmail(event.target.value)}
            data-testid={`${testIdPrefix}-email-input`}
            autoComplete="off"
            className="w-full"
          />
        </div>
        <div style={{ width: 160 }}>
          <Select
            options={ROLE_OPTIONS}
            value={newRole}
            onChange={setNewRole}
            disabled={busy}
            testId={`${testIdPrefix}-new-role-select`}
          />
        </div>
        <Button
          type="submit"
          disabled={busy || !newEmail.trim()}
          waiting={busy}
          data-testid={`${testIdPrefix}-add-button`}
        >
          Add member
        </Button>
      </form>
      {formError && (
        <Typography
          variant="body"
          size="small"
          className="text-negative-content mb-base"
          data-testid={`${testIdPrefix}-form-error`}
        >
          {formError}
        </Typography>
      )}

      <table className="w-full text-left" data-testid={`${testIdPrefix}-table`}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {members.map((member) => {
            const isInherited = member.role === null && !!member.workspace_role;
            const showWorkspaceHint = member.role !== null && !!member.workspace_role;

            return (
              <tr key={member.user} data-testid={`${testIdPrefix}-row-${member.user}`}>
                <td>
                  {getDisplayName(member)} {member.is_owner && <Badge>Owner</Badge>}
                </td>
                <td>{member.email}</td>
                <td style={{ width: 160 }}>
                  {isInherited ? (
                    <span>
                      {getRoleLabel(member.workspace_role)}{" "}
                      <Badge size="small" data-testid={`${testIdPrefix}-inherited-${member.user}`}>
                        via workspace
                      </Badge>
                    </span>
                  ) : (
                    <>
                      <Select
                        options={ROLE_OPTIONS}
                        value={member.role}
                        onChange={(role) => changeRole(member, role)}
                        disabled={busy || member.is_owner}
                        testId={`${testIdPrefix}-role-select-${member.user}`}
                      />
                      {showWorkspaceHint && (
                        <Typography variant="body" size="small" className="text-neutral-content-subtler">
                          workspace: {getRoleLabel(member.workspace_role)}
                        </Typography>
                      )}
                    </>
                  )}
                </td>
                <td>
                  {!member.is_owner && !isInherited && (
                    <Button
                      variant="negative"
                      look="outlined"
                      disabled={busy}
                      onClick={() => confirmRemoval(member)}
                      data-testid={`${testIdPrefix}-remove-button-${member.user}`}
                    >
                      Remove
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
};
