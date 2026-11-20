import { Badge, Button, Tooltip, useToast } from "@humansignal/ui";
import { useCallback, useContext, useEffect, useState } from "react";
import { IconSpark } from "@humansignal/icons";
import { Form, Input, TextArea } from "../../components/Form";
import { confirm } from "../../components/Modal/Modal";
import { WorkspaceSelect } from "../../components/WorkspaceSelect/WorkspaceSelect";
import { useAPI } from "../../providers/ApiProvider";
import { RadioGroup } from "../../components/Form/Elements/RadioGroup/RadioGroup";
import { ProjectContext } from "../../providers/ProjectProvider";
import { cn } from "../../utils/bem";
import { HeidiTips } from "../../components/HeidiTips/HeidiTips";
import { FF_LSDV_E_297, isFF } from "../../utils/feature-flags";
import { createURL } from "../../components/HeidiTips/utils";

export const GeneralSettings = () => {
  const { project, fetchProject } = useContext(ProjectContext);

  const api = useAPI();
  const toast = useToast();
  const [workspaceState, setWorkspaceState] = useState({ workspace: null, can_change: false });
  const [workspaceSelectVersion, setWorkspaceSelectVersion] = useState(0);

  const projectId = project?.id;

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;

    const fetchWorkspace = async () => {
      const result = await api.callApi("projectWorkspace", { params: { pk: projectId }, suppressError: true });
      if (cancelled || result?.error) return;
      setWorkspaceState({ workspace: result?.workspace ?? null, can_change: !!result?.can_change });
    };

    fetchWorkspace();
    return () => {
      cancelled = true;
    };
  }, [api, projectId]);

  const applyWorkspace = async (workspaceId) => {
    const result = await api.callApi("setProjectWorkspace", {
      params: { pk: projectId },
      body: { workspace: workspaceId },
      suppressError: true,
    });

    if (result?.error) {
      toast.show({ message: result.response?.detail ?? "Could not update the workspace", type: "error" });
      return;
    }
    toast.show({ message: "Workspace updated" });
    setWorkspaceState({ workspace: result?.workspace ?? null, can_change: !!result?.can_change });
  };

  const changeWorkspace = (workspaceId, workspaceTitle) => {
    // The select keeps the clicked option by itself. Remounting it shows the saved workspace again until
    // the server accepts the change, which also covers a cancelled confirmation and a refusal.
    setWorkspaceSelectVersion((version) => version + 1);
    if (workspaceId === null) {
      applyWorkspace(null);
      return;
    }
    confirm({
      title: "Change workspace",
      body: `Members of ${workspaceTitle} will get access to this project.`,
      okText: "Change",
      onOk: () => applyWorkspace(workspaceId),
    });
  };

  const updateProject = useCallback(() => {
    if (project.id) fetchProject(project.id, true);
  }, [project]);

  const colors = ["#FDFDFC", "#FF4C25", "#FF750F", "#ECB800", "#9AC422", "#34988D", "#617ADA", "#CC6FBE"];

  const samplings = [
    { value: "Sequential", label: "Sequential", description: "Tasks are ordered by Task ID" },
    { value: "Uniform", label: "Random", description: "Tasks are chosen with uniform random" },
  ];

  return (
    <div className={cn("general-settings").toClassName()}>
      <div className={cn("general-settings").elem("wrapper").toClassName()}>
        <h1>General Settings</h1>
        <div className={cn("settings-wrapper").toClassName()}>
          <Form action="updateProject" formData={{ ...project }} params={{ pk: project.id }} onSubmit={updateProject}>
            <Form.Row columnCount={1} rowGap="16px">
              <Input name="title" label="Project Name" />

              <TextArea name="description" label="Description" style={{ minHeight: 128 }} />
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-neutral-content">Workspace</label>
                <WorkspaceSelect
                  key={workspaceSelectVersion}
                  value={workspaceState.workspace?.id ?? null}
                  extraOption={workspaceState.workspace}
                  disabled={!workspaceState.can_change}
                  onChange={changeWorkspace}
                />
                <span className="text-neutral-content-subtler">
                  Members of the workspace get their workspace role on this project.
                </span>
              </div>
              <RadioGroup name="color" label="Color" size="large" labelProps={{ size: "large" }}>
                {colors.map((color) => (
                  <RadioGroup.Button key={color} value={color}>
                    <div className={cn("color").toClassName()} style={{ "--background": color }} />
                  </RadioGroup.Button>
                ))}
              </RadioGroup>

              <RadioGroup label="Task Sampling" labelProps={{ size: "large" }} name="sampling" simple>
                {samplings.map(({ value, label, description }) => (
                  <RadioGroup.Button
                    key={value}
                    value={`${value} sampling`}
                    label={`${label} sampling`}
                    description={description}
                  />
                ))}
                {isFF(FF_LSDV_E_297) && (
                  <RadioGroup.Button
                    key="uncertainty-sampling"
                    value=""
                    label={
                      <>
                        Uncertainty sampling{" "}
                        <Tooltip title="Available on Label Studio Enterprise">
                          <Badge
                            variant="enterprise"
                            icon={<IconSpark />}
                            size="small"
                            look="ghost"
                            className="ml-tightest"
                          />
                        </Tooltip>
                      </>
                    }
                    disabled
                    description={
                      <>
                        Tasks are chosen according to model uncertainty score (active learning mode).{" "}
                        <a
                          target="_blank"
                          href={createURL("https://docs.humansignal.com/guide/active_learning", {
                            experiment: "project_settings_workspace",
                            treatment: "workspaces",
                          })}
                          rel="noreferrer"
                        >
                          Learn more
                        </a>
                      </>
                    }
                  />
                )}
              </RadioGroup>
            </Form.Row>

            <Form.Actions>
              <Form.Indicator>
                <span case="success">Saved!</span>
              </Form.Indicator>
              <Button type="submit" className="w-[150px]" aria-label="Save general settings">
                Save
              </Button>
            </Form.Actions>
          </Form>
        </div>
      </div>
      {isFF(FF_LSDV_E_297) && <HeidiTips collection="projectSettings" />}
    </div>
  );
};

GeneralSettings.menuItem = "General";
GeneralSettings.path = "/";
GeneralSettings.exact = true;
