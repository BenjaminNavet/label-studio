import { Button } from "@humansignal/ui";
import { cn } from "../../utils/bem";

const SidebarEntry = ({ testId, selected, onSelect, color, label, count, children }) => {
  const block = cn("workspaces-sidebar");

  return (
    <li className={block.elem("row").mod({ selected }).toClassName()}>
      <button type="button" className={block.elem("entry").toClassName()} onClick={onSelect} data-testid={testId}>
        {color !== undefined && (
          <span className={block.elem("dot").toClassName()} style={{ "--workspace-color": color }} />
        )}
        <span className={block.elem("label").toClassName()}>{label}</span>
        {count !== undefined && <span className={block.elem("count").toClassName()}>{count}</span>}
      </button>
      {children}
    </li>
  );
};

/** Left column of the Projects page: "All projects", the workspaces, then "No workspace". */
export const WorkspacesSidebar = ({ workspaces, selected, onSelect, onCreate, onEdit }) => {
  const block = cn("workspaces-sidebar");

  return (
    <aside className={block.toClassName()} data-testid="workspaces-sidebar">
      <ul className={block.elem("list").toClassName()}>
        <SidebarEntry
          testId="workspace-item-all"
          selected={selected === null}
          onSelect={() => onSelect(null)}
          label="All projects"
        />
        {workspaces.map((workspace) => (
          <SidebarEntry
            key={workspace.id}
            testId={`workspace-item-${workspace.id}`}
            selected={selected === workspace.id}
            onSelect={() => onSelect(workspace.id)}
            color={workspace.color || "var(--color-neutral-border)"}
            label={workspace.title}
            count={workspace.project_count}
          >
            {workspace.can_manage && (
              <button
                type="button"
                className={block.elem("settings").toClassName()}
                onClick={() => onEdit(workspace)}
                aria-label={`Settings of workspace ${workspace.title}`}
                title="Workspace settings"
                data-testid={`workspace-settings-button-${workspace.id}`}
              >
                &#9881;
              </button>
            )}
          </SidebarEntry>
        ))}
        <SidebarEntry
          testId="workspace-item-none"
          selected={selected === "none"}
          onSelect={() => onSelect("none")}
          label="No workspace"
        />
      </ul>
      <div className={block.elem("footer").toClassName()}>
        <Button size="small" look="outlined" onClick={onCreate} data-testid="workspace-create-button">
          New workspace
        </Button>
      </div>
    </aside>
  );
};
