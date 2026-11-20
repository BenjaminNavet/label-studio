import React, { useState } from "react";
import { useParams as useRouterParams } from "react-router";
import { Redirect } from "react-router-dom";
import { Button } from "@humansignal/ui";
import { Oneof } from "../../components/Oneof/Oneof";
import { Spinner } from "../../components/Spinner/Spinner";
import { ApiContext } from "../../providers/ApiProvider";
import { useContextProps } from "../../providers/RoutesProvider";
import { cn } from "../../utils/bem";
import { CreateProject } from "../CreateProject/CreateProject";
import { DataManagerPage } from "../DataManager/DataManager";
import { SettingsPage } from "../Settings";
import { WorkspaceModal } from "./WorkspaceModal";
import { WorkspacesSidebar } from "./WorkspacesSidebar";
import { EmptyProjectsList, ProjectsList } from "./ProjectsList";
import { useAbortController, useUpdatePageTitle } from "@humansignal/core";
import "./Projects.prefix.css";

const getCurrentPage = () => {
  const pageNumberFromURL = new URLSearchParams(location.search).get("page");

  return pageNumberFromURL ? Number.parseInt(pageNumberFromURL) : 1;
};

/** Workspace filter from the URL: `null` (all projects), "none" or a workspace id. */
const getCurrentWorkspace = () => {
  const workspaceFromURL = new URLSearchParams(location.search).get("workspace");

  if (workspaceFromURL === "none") return "none";
  const workspaceId = Number.parseInt(workspaceFromURL ?? "", 10);

  return Number.isNaN(workspaceId) ? null : workspaceId;
};

export const ProjectsPage = () => {
  const api = React.useContext(ApiContext);
  const abortController = useAbortController();
  const [projectsList, setProjectsList] = React.useState([]);
  const [networkState, setNetworkState] = React.useState(null);
  const [currentPage, setCurrentPage] = useState(getCurrentPage());
  const [totalItems, setTotalItems] = useState(1);
  const [workspaces, setWorkspaces] = useState([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState(getCurrentWorkspace());
  // `false` = closed, `true` = creation, a workspace object = settings
  const [workspaceModal, setWorkspaceModal] = useState(false);
  const setContextProps = useContextProps();

  useUpdatePageTitle("Projects");
  const defaultPageSize = Number.parseInt(localStorage.getItem("pages:projects-list") ?? 30);

  const [modal, setModal] = React.useState(false);

  const openModal = () => setModal(true);

  const closeModal = () => setModal(false);

  const fetchWorkspaces = async () => {
    const result = await api.callApi("workspaces", { suppressError: true });

    if (Array.isArray(result)) {
      setWorkspaces(result);
      return result;
    }
    return null;
  };

  const updateWorkspaceInURL = (workspace) => {
    const searchParams = new URLSearchParams(location.search);

    searchParams.delete("page");
    if (workspace === null) searchParams.delete("workspace");
    else searchParams.set("workspace", String(workspace));
    const search = searchParams.toString();

    history.replaceState(null, "", `${location.pathname}${search ? `?${search}` : ""}${location.hash}`);
  };

  const fetchProjects = async (page = currentPage, pageSize = defaultPageSize, workspace = selectedWorkspace) => {
    setNetworkState("loading");
    abortController.renew(); // Cancel any in flight requests

    const requestParams = { page, page_size: pageSize };

    requestParams.include = [
      "id",
      "title",
      "created_by",
      "created_at",
      "color",
      "is_published",
      "assignment_settings",
      "state",
    ].join(",");

    if (workspace !== null) requestParams.workspace = workspace;

    const data = await api.callApi("projects", {
      params: requestParams,
      signal: abortController.controller.current.signal,
      errorFilter: (e) => e.error.includes("aborted"),
    });

    setTotalItems(data?.count ?? 1);
    setProjectsList(data.results ?? []);
    setNetworkState("loaded");

    if (data?.results?.length) {
      const additionalData = await api.callApi("projects", {
        params: {
          ids: data?.results?.map(({ id }) => id).join(","),
          include: [
            "id",
            "description",
            "num_tasks_with_annotations",
            "task_number",
            "skipped_annotations_number",
            "total_annotations_number",
            "total_predictions_number",
            "ground_truth_number",
            "finished_task_number",
          ].join(","),
          page_size: pageSize,
        },
        signal: abortController.controller.current.signal,
        errorFilter: (e) => e.error.includes("aborted"),
      });

      if (additionalData?.results?.length) {
        setProjectsList((prev) =>
          additionalData.results.map((project) => {
            const prevProject = prev.find(({ id }) => id === project.id);

            return {
              ...prevProject,
              ...project,
            };
          }),
        );
      }
    }
  };

  const loadNextPage = async (page, pageSize) => {
    setCurrentPage(page);
    await fetchProjects(page, pageSize);
  };

  const selectWorkspace = async (workspace) => {
    setSelectedWorkspace(workspace);
    setCurrentPage(1);
    updateWorkspaceInURL(workspace);
    await fetchProjects(1, defaultPageSize, workspace);
  };

  const refreshWorkspaces = async () => {
    const fetchedWorkspaces = await fetchWorkspaces();
    const isSelectionMissing =
      typeof selectedWorkspace === "number" &&
      fetchedWorkspaces !== null &&
      !fetchedWorkspaces.some(({ id }) => id === selectedWorkspace);

    if (isSelectionMissing) {
      await selectWorkspace(null);
      return;
    }
    await fetchProjects(currentPage, defaultPageSize, selectedWorkspace);
  };

  const closeWorkspaceModal = () => setWorkspaceModal(false);

  const handleWorkspaceSaved = async (savedWorkspace) => {
    closeWorkspaceModal();
    await refreshWorkspaces();
    // Creating a workspace selects it so that its (empty) content is shown right away
    if (workspaceModal === true && savedWorkspace?.id) await selectWorkspace(savedWorkspace.id);
  };

  const handleWorkspaceDeleted = async () => {
    closeWorkspaceModal();
    // Falls back to all projects when the deleted workspace was the selected one
    await refreshWorkspaces();
  };

  React.useEffect(() => {
    // The selection can point to a deleted workspace: fall back to all projects.
    fetchWorkspaces().then((fetchedWorkspaces) => {
      const isSelectionMissing =
        typeof selectedWorkspace === "number" &&
        fetchedWorkspaces !== null &&
        !fetchedWorkspaces.some(({ id }) => id === selectedWorkspace);

      if (isSelectionMissing) {
        selectWorkspace(null);
      } else {
        fetchProjects();
      }
    });
  }, []);

  const hasActiveFilter = selectedWorkspace !== null;

  React.useEffect(() => {
    // there is a nice page with Create button when list is empty
    // so don't show the context button in that case (unless a filter is active)
    setContextProps({ openModal, showButton: projectsList.length > 0 || hasActiveFilter });
  }, [projectsList.length, hasActiveFilter]);

  const selectedWorkspaceObject = workspaces.find(({ id }) => id === selectedWorkspace);
  const defaultWorkspaceId = selectedWorkspaceObject?.can_manage ? selectedWorkspaceObject.id : null;

  return (
    <div className={cn("projects-page").toClassName()}>
      <Oneof value={networkState}>
        <div className={cn("projects-page").elem("loading").toClassName()} case="loading">
          <Spinner size={64} />
        </div>
        <div className={cn("projects-page").elem("content").toClassName()} case="loaded">
          <WorkspacesSidebar
            workspaces={workspaces}
            selected={selectedWorkspace}
            onSelect={selectWorkspace}
            onCreate={() => setWorkspaceModal(true)}
            onEdit={setWorkspaceModal}
          />
          <div className={cn("projects-page").elem("main").toClassName()}>
            {projectsList.length ? (
              <ProjectsList
                projects={projectsList}
                currentPage={currentPage}
                totalItems={totalItems}
                loadNextPage={loadNextPage}
                pageSize={defaultPageSize}
              />
            ) : hasActiveFilter ? (
              <div
                className={cn("projects-page").elem("empty-filter").toClassName()}
                data-testid="projects-empty-filter"
              >
                <p>No projects in this workspace</p>
                <Button onClick={openModal} size="small" aria-label="Create new project">
                  Create
                </Button>
              </div>
            ) : (
              <EmptyProjectsList openModal={openModal} />
            )}
          </div>
          {modal && <CreateProject onClose={closeModal} defaultWorkspaceId={defaultWorkspaceId} />}
          {workspaceModal !== false && (
            <WorkspaceModal
              workspace={workspaceModal === true ? undefined : workspaceModal}
              onClose={closeWorkspaceModal}
              onSaved={handleWorkspaceSaved}
              onDeleted={handleWorkspaceDeleted}
            />
          )}
        </div>
      </Oneof>
    </div>
  );
};

ProjectsPage.title = "Projects";
ProjectsPage.path = "/projects";
ProjectsPage.exact = true;
ProjectsPage.routes = ({ store }) => [
  {
    title: () => store.project?.title,
    path: "/:id(\\d+)",
    exact: true,
    component: () => {
      const params = useRouterParams();

      return <Redirect to={`/projects/${params.id}/data`} />;
    },
    pages: {
      DataManagerPage,
      SettingsPage,
    },
  },
];
ProjectsPage.context = ({ openModal, showButton }) => {
  if (!showButton) return null;
  return (
    <Button onClick={openModal} size="small" aria-label="Create new project">
      Create
    </Button>
  );
};
