import { useEffect, useState } from "react";
import { useAPI } from "../providers/ApiProvider";

// One request per page load: the answer only changes when an administrator edits the account.
let pendingRequest = null;

/**
 * What the current user may do outside projects (project_rbac, `/api/rbac/me/`).
 * Returns `null` while loading, then `{ is_admin: boolean }`.
 * The server enforces every right; this only decides what the interface shows.
 */
export const useRbacMe = () => {
  const api = useAPI();
  const [me, setMe] = useState(null);

  useEffect(() => {
    let cancelled = false;

    pendingRequest ??= api.callApi("rbacMe", { suppressError: true });
    pendingRequest.then((result) => {
      if (!cancelled) setMe({ is_admin: result?.is_admin === true });
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return me;
};
