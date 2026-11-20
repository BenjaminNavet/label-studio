import { useState } from "react";
import { Typography } from "@humansignal/ui";
import { useUpdatePageTitle, createTitleFromSegments } from "@humansignal/core";
import { RoleMembers } from "../../../components/RoleMembers/RoleMembers";
import { useProject } from "../../../providers/ProjectProvider";
import { cn } from "../../../utils/bem";

const ROLE_LEGEND = [
  { role: "Manager", description: "full project settings, import/export, members." },
  { role: "Reviewer", description: "annotate and edit or delete any annotation." },
  { role: "Annotator", description: "annotate and edit or delete their own annotations." },
];

export const MembersSettings = () => {
  const { project } = useProject();
  const [forbidden, setForbidden] = useState(false);

  useUpdatePageTitle(createTitleFromSegments([project?.title, "Members"]));

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
      <RoleMembers
        listEndpoint="projectRoles"
        assignEndpoint="assignProjectRole"
        revokeEndpoint="revokeProjectRole"
        pk={project?.id}
        scopeLabel="project"
        onForbiddenChange={setForbidden}
      />
    </div>
  );
};

MembersSettings.title = "Members";
MembersSettings.path = "/members";
