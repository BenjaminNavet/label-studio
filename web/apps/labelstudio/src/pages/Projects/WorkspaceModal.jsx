import { useState } from "react";
import { Button, Typography } from "@humansignal/ui";
import Input from "../../components/Form/Elements/Input/Input";
import { Modal, confirm } from "../../components/Modal/Modal";
import { RoleMembers } from "../../components/RoleMembers/RoleMembers";
import { Space } from "../../components/Space/Space";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";

const WORKSPACE_COLORS = ["#FDFDFC", "#FF4C25", "#FF750F", "#ECB800", "#9AC422", "#34988D", "#617ADA", "#CC6FBE"];

/** First validation message of a failed API result, the server `detail` otherwise. */
const extractErrorMessage = (result) => {
  const body = result?.response ?? {};
  const validationErrors = body.validation_errors;

  if (validationErrors && typeof validationErrors === "object") {
    for (const messages of Object.values(validationErrors)) {
      const first = Array.isArray(messages) ? messages[0] : messages;

      if (first) return String(first);
    }
  }
  return body.detail || result?.error || "Unexpected error";
};

/** Create a workspace (no `workspace` prop) or edit the settings of an existing one. */
export const WorkspaceModal = ({ workspace, onClose, onSaved, onDeleted }) => {
  const api = useAPI();
  const block = cn("workspace-modal");
  const isEdit = Boolean(workspace);
  const [title, setTitle] = useState(workspace?.title ?? "");
  const [color, setColor] = useState(workspace?.color ?? WORKSPACE_COLORS[0]);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const save = async () => {
    setSubmitting(true);
    setError(null);
    const body = { title: title.trim(), color };
    const result = isEdit
      ? await api.callApi("updateWorkspace", { params: { pk: workspace.id }, body, suppressError: true })
      : await api.callApi("createWorkspace", { body, suppressError: true });

    setSubmitting(false);
    if (result?.error) {
      setError(extractErrorMessage(result));
      return;
    }
    onSaved?.(result);
  };

  const deleteWorkspace = async () => {
    const result = await api.callApi("deleteWorkspace", { params: { pk: workspace.id }, suppressError: true });

    if (result?.error) {
      setError(extractErrorMessage(result));
      return;
    }
    onDeleted?.(workspace);
  };

  const confirmDelete = () => {
    confirm({
      title: "Delete workspace",
      body:
        `Delete the workspace "${workspace.title}"? Its projects are kept: ` +
        `they are only detached from the workspace and will appear under "No workspace".`,
      okText: "Delete",
      buttonLook: "negative",
      onOk: deleteWorkspace,
    });
  };

  return (
    <Modal
      visible
      title={isEdit ? "Workspace settings" : "New workspace"}
      width={560}
      closeOnClickOutside={false}
      onHide={onClose}
      data-testid="workspace-modal"
    >
      <div className={block.toClassName()}>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
        >
          <div className="flex flex-col gap-base">
            <Input
              label="Title"
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              autoComplete="off"
              data-testid="workspace-title-input"
            />
            <div className={block.elem("colors").toClassName()} role="radiogroup" aria-label="Color">
              {WORKSPACE_COLORS.map((workspaceColor) => (
                <button
                  key={workspaceColor}
                  type="button"
                  role="radio"
                  aria-checked={color === workspaceColor}
                  aria-label={`Color ${workspaceColor}`}
                  className={block.elem("color").mod({ selected: color === workspaceColor }).toClassName()}
                  style={{ "--workspace-color": workspaceColor }}
                  onClick={() => setColor(workspaceColor)}
                />
              ))}
            </div>
            {error && (
              <Typography
                variant="body"
                size="small"
                className="text-negative-content"
                data-testid="workspace-modal-error"
              >
                {error}
              </Typography>
            )}
            <Space align="end">
              {isEdit && workspace.can_delete && (
                <Button
                  type="button"
                  variant="negative"
                  look="outlined"
                  onClick={confirmDelete}
                  data-testid="workspace-delete-button"
                >
                  Delete
                </Button>
              )}
              <Button type="button" variant="neutral" look="outlined" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" waiting={submitting} disabled={!title.trim()} data-testid="workspace-save-button">
                Save
              </Button>
            </Space>
          </div>
        </form>
        {isEdit && workspace.can_manage && (
          <div className={block.elem("members").toClassName()}>
            <Typography variant="headline" size="medium">
              Members
            </Typography>
            <RoleMembers
              listEndpoint="workspaceRoles"
              assignEndpoint="assignWorkspaceRole"
              revokeEndpoint="revokeWorkspaceRole"
              pk={workspace.id}
              scopeLabel="workspace"
              testIdPrefix="workspace-members"
            />
          </div>
        )}
      </div>
    </Modal>
  );
};
