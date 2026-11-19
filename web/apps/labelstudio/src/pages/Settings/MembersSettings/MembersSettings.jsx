import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Select, Typography, useToast } from "@humansignal/ui";
import { useUpdatePageTitle, createTitleFromSegments } from "@humansignal/core";
import Input from "../../../components/Form/Elements/Input/Input";
import { confirm } from "../../../components/Modal/Modal";
import { Spinner } from "../../../components/Spinner/Spinner";
import { useAPI } from "../../../providers/ApiProvider";
import { useProject } from "../../../providers/ProjectProvider";
import { cn } from "../../../utils/bem";

const ROLE_OPTIONS = [
  { value: "manager", label: "Manager" },
  { value: "reviewer", label: "Reviewer" },
  { value: "annotator", label: "Annotator" },
];

const ROLE_LEGEND = [
  { role: "Manager", description: "full project settings, import/export, members." },
  { role: "Reviewer", description: "annotate and edit or delete any annotation." },
  { role: "Annotator", description: "annotate and edit or delete their own annotations." },
];

const getDisplayName = (member) => `${member.first_name ?? ""} ${member.last_name ?? ""}`.trim() || member.email;

const getFirstErrorMessage = (result) => {
  const validationErrors = result?.response?.validation_errors;
  const firstFieldMessage = validationErrors?.email?.[0] ?? validationErrors?.role?.[0];
  return firstFieldMessage ?? validationErrors?.non_field_errors?.[0] ?? result?.response?.detail ?? "Request failed";
};

export const MembersSettings = () => {
  const { project } = useProject();
  const api = useAPI();
  const toast = useToast();

  const [members, setMembers] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [forbidden, setForbidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("annotator");
  const [formError, setFormError] = useState(null);

  useUpdatePageTitle(createTitleFromSegments([project?.title, "Members"]));

  const fetchMembers = useCallback(async () => {
    if (!project?.id) return;
    const result = await api.callApi("projectRoles", { params: { pk: project.id }, suppressError: true });

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
  }, [api, project?.id]);

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
      const result = await api.callApi("assignProjectRole", {
        params: { pk: project.id },
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
      const result = await api.callApi("assignProjectRole", {
        params: { pk: project.id },
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
      const result = await api.callApi("revokeProjectRole", {
        params: { pk: project.id, userPk: member.user },
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
      body: `Remove ${getDisplayName(member)} from this project?`,
      okText: "Remove",
      buttonLook: "negative",
      onOk: () => removeMember(member),
    });
  };

  let content;
  if (forbidden) {
    content = <Typography variant="body">Only project managers can manage members.</Typography>;
  } else if (loadError) {
    content = (
      <Typography variant="body" className="text-negative-content" data-testid="members-load-error">
        Could not load members: {loadError}
      </Typography>
    );
  } else if (!members) {
    content = (
      <div style={{ display: "flex", justifyContent: "center", marginTop: 32 }}>
        <Spinner size={32} />
      </div>
    );
  } else {
    content = (
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
              data-testid="members-email-input"
              autoComplete="off"
            />
          </div>
          <div style={{ width: 160 }}>
            <Select
              options={ROLE_OPTIONS}
              value={newRole}
              onChange={setNewRole}
              disabled={busy}
              testId="members-new-role-select"
            />
          </div>
          <Button type="submit" disabled={busy || !newEmail.trim()} waiting={busy} data-testid="members-add-button">
            Add member
          </Button>
        </form>
        {formError && (
          <Typography
            variant="body"
            size="small"
            className="text-negative-content mb-base"
            data-testid="members-form-error"
          >
            {formError}
          </Typography>
        )}

        <table className="w-full text-left" data-testid="members-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr key={member.user} data-testid={`members-row-${member.user}`}>
                <td>
                  {getDisplayName(member)} {member.is_owner && <Badge>Owner</Badge>}
                </td>
                <td>{member.email}</td>
                <td style={{ width: 160 }}>
                  <Select
                    options={ROLE_OPTIONS}
                    value={member.role}
                    onChange={(role) => changeRole(member, role)}
                    disabled={busy || member.is_owner}
                    testId={`members-role-select-${member.user}`}
                  />
                </td>
                <td>
                  {!member.is_owner && (
                    <Button
                      variant="negative"
                      look="outlined"
                      disabled={busy}
                      onClick={() => confirmRemoval(member)}
                      data-testid={`members-remove-button-${member.user}`}
                    >
                      Remove
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </>
    );
  }

  return (
    <div className={cn("simple-settings").toClassName()} style={{ width: "48rem" }}>
      <Typography variant="headline" size="medium" className="mb-tighter">
        Members
      </Typography>
      {!forbidden && (
        <ul className="mb-base text-neutral-content-subtler" data-testid="members-legend">
          {ROLE_LEGEND.map(({ role, description }) => (
            <li key={role}>
              <strong>{role}</strong> - {description}
            </li>
          ))}
        </ul>
      )}
      {content}
    </div>
  );
};

MembersSettings.title = "Members";
MembersSettings.path = "/members";
