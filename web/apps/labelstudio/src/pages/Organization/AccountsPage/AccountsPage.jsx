import { formatDistance } from "date-fns";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Checkbox, Typography, useToast } from "@humansignal/ui";
import { useUpdatePageTitle } from "@humansignal/core";
import { Input } from "../../../components/Form";
import { modal } from "../../../components/Modal/Modal";
import { useModalControls } from "../../../components/Modal/ModalPopup";
import { Space } from "../../../components/Space/Space";
import { Spinner } from "../../../components/Spinner/Spinner";
import { useCopyText } from "../../../hooks/useCopyText";
import { useRbacMe } from "../../../hooks/useRbacMe";
import { useAPI } from "../../../providers/ApiProvider";

/**
 * Turn a failed API result into one human-readable message:
 * the first validation message when there is one, the server `detail` otherwise.
 */
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

const fullName = (account) => [account.first_name, account.last_name].filter(Boolean).join(" ");

/** Modal content: a form whose submission is delegated to `onSubmit(values)` (returns an error message or null). */
const AccountForm = ({ initialValues, submitLabel, adminLocked, onSubmit, testIdPrefix }) => {
  const ctrl = useModalControls();
  const [values, setValues] = useState(initialValues);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const setField = (field) => (event) => setValues((previous) => ({ ...previous, [field]: event.target.value }));

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    const errorMessage = await onSubmit(values);

    setSubmitting(false);
    if (errorMessage) {
      setError(errorMessage);
    } else {
      ctrl?.hide();
    }
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div className="flex flex-col gap-base">
        <Input
          label="Email"
          type="email"
          required
          value={values.email}
          onChange={setField("email")}
          autoComplete="off"
          data-testid={`${testIdPrefix}-email`}
        />
        <Input
          label="First name"
          value={values.first_name}
          onChange={setField("first_name")}
          autoComplete="off"
          data-testid={`${testIdPrefix}-first-name`}
        />
        <Input
          label="Last name"
          value={values.last_name}
          onChange={setField("last_name")}
          autoComplete="off"
          data-testid={`${testIdPrefix}-last-name`}
        />
        <Checkbox
          checked={values.is_admin}
          disabled={adminLocked}
          onChange={(event) => setValues((previous) => ({ ...previous, is_admin: event.target.checked }))}
          data-testid={`${testIdPrefix}-is-admin`}
        >
          Administrator
        </Checkbox>
        {error && (
          <Typography
            variant="body"
            size="small"
            className="text-negative-content"
            data-testid={`${testIdPrefix}-error`}
          >
            {error}
          </Typography>
        )}
        <Space align="end">
          <Button
            type="button"
            variant="neutral"
            look="outlined"
            onClick={() => ctrl?.hide()}
            data-testid={`${testIdPrefix}-cancel`}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            waiting={submitting}
            disabled={!values.email.trim()}
            data-testid={`${testIdPrefix}-submit`}
          >
            {submitLabel}
          </Button>
        </Space>
      </div>
    </form>
  );
};

/** Modal content: confirmation of an action, with the server error shown inline when it fails. */
const ConfirmAction = ({ message, confirmLabel, destructive, onConfirm }) => {
  const ctrl = useModalControls();
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const confirm = async () => {
    setSubmitting(true);
    setError(null);
    const errorMessage = await onConfirm();

    setSubmitting(false);
    if (errorMessage) {
      setError(errorMessage);
    } else {
      ctrl?.hide();
    }
  };

  return (
    <div className="flex flex-col gap-base">
      <Typography variant="body" size="medium">
        {message}
      </Typography>
      {error && (
        <Typography variant="body" size="small" className="text-negative-content" data-testid="accounts-confirm-error">
          {error}
        </Typography>
      )}
      <Space align="end">
        <Button variant="neutral" look="outlined" onClick={() => ctrl?.hide()} data-testid="accounts-confirm-cancel">
          Cancel
        </Button>
        <Button
          variant={destructive ? "negative" : "primary"}
          waiting={submitting}
          onClick={confirm}
          data-testid="accounts-confirm-submit"
        >
          {confirmLabel}
        </Button>
      </Space>
    </div>
  );
};

/** Modal content: the generated password, shown once. */
const PasswordReveal = ({ email, password }) => {
  const ctrl = useModalControls();
  const [copied, copyPassword] = useCopyText({ defaultText: password });

  return (
    <div className="flex flex-col gap-base">
      <Typography variant="body" size="medium">
        Email: <strong data-testid="accounts-password-email">{email}</strong>
      </Typography>
      <div className="flex items-center gap-tight">
        <code
          className="flex-1 p-tight bg-neutral-surface rounded-small select-all"
          data-testid="accounts-password-value"
        >
          {password}
        </code>
        <Button look="outlined" onClick={() => copyPassword()} data-testid="accounts-password-copy">
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <Typography variant="body" size="small" className="text-neutral-content-subtler">
        This password is shown only once. Send it to the user through a private channel.
      </Typography>
      <Space align="end">
        <Button onClick={() => ctrl?.hide()} data-testid="accounts-password-close">
          Close
        </Button>
      </Space>
    </div>
  );
};

export const AccountsPage = () => {
  const api = useAPI();
  const toast = useToast();
  const me = useRbacMe();
  const isAdmin = me?.is_admin === true;
  const currentUserId = window.APP_SETTINGS?.user?.id;
  const [accounts, setAccounts] = useState(null);
  const [loadError, setLoadError] = useState(null);

  useUpdatePageTitle("Accounts");

  const refresh = useCallback(async () => {
    const result = await api.callApi("accounts", { suppressError: true });

    if (result?.error || !Array.isArray(result)) {
      const message = extractErrorMessage(result);

      setLoadError(message);
      toast.show({ message, type: "error" });
      return;
    }
    setLoadError(null);
    setAccounts(result);
  }, [api]);

  useEffect(() => {
    if (isAdmin) refresh();
  }, [isAdmin, refresh]);

  const showPassword = (email, password) => {
    modal({
      title: "Generated password",
      width: 520,
      allowClose: false,
      body: () => <PasswordReveal email={email} password={password} />,
    });
  };

  /** PATCH an account; returns an error message or null. */
  const patchAccount = async (account, body) => {
    const result = await api.callApi("updateAccount", { params: { pk: account.id }, body, suppressError: true });

    if (result?.error) return extractErrorMessage(result);
    await refresh();
    return null;
  };

  const openCreate = () => {
    modal({
      title: "Create account",
      width: 520,
      allowClose: false,
      body: () => (
        <AccountForm
          testIdPrefix="accounts-create"
          submitLabel="Create account"
          initialValues={{ email: "", first_name: "", last_name: "", is_admin: false }}
          onSubmit={async (values) => {
            const result = await api.callApi("createAccount", {
              body: { ...values, email: values.email.trim() },
              suppressError: true,
            });

            if (result?.error) return extractErrorMessage(result);
            await refresh();
            // The create modal is hidden once this resolves; open the password one after it.
            setTimeout(() => showPassword(result.email ?? values.email, result.password), 0);
            return null;
          }}
        />
      ),
    });
  };

  const openEdit = (account, adminLocked) => {
    modal({
      title: "Edit account",
      width: 520,
      allowClose: false,
      body: () => (
        <AccountForm
          testIdPrefix="accounts-edit"
          submitLabel="Save"
          adminLocked={adminLocked}
          initialValues={{
            email: account.email ?? "",
            first_name: account.first_name ?? "",
            last_name: account.last_name ?? "",
            is_admin: account.is_admin,
          }}
          onSubmit={async (values) => {
            const body = {
              email: values.email.trim(),
              first_name: values.first_name,
              last_name: values.last_name,
            };

            if (!adminLocked) body.is_admin = values.is_admin;
            const errorMessage = await patchAccount(account, body);

            if (!errorMessage) toast.show({ message: "Account updated" });
            return errorMessage;
          }}
        />
      ),
    });
  };

  const openToggleActive = (account) => {
    const activating = !account.is_active;
    const label = fullName(account) || account.email;

    modal({
      title: activating ? "Reactivate account" : "Deactivate account",
      width: 520,
      allowClose: false,
      body: () => (
        <ConfirmAction
          destructive={!activating}
          confirmLabel={activating ? "Reactivate" : "Deactivate"}
          message={
            activating
              ? `${label} will be able to sign in again.`
              : `${label} will no longer be able to sign in. Their annotations and project memberships are kept.`
          }
          onConfirm={async () => {
            const errorMessage = await patchAccount(account, { is_active: activating });

            if (!errorMessage) toast.show({ message: activating ? "Account reactivated" : "Account deactivated" });
            return errorMessage;
          }}
        />
      ),
    });
  };

  const openResetPassword = (account) => {
    modal({
      title: "Reset password",
      width: 520,
      allowClose: false,
      body: () => (
        <ConfirmAction
          destructive
          confirmLabel="Reset password"
          message={`A new password will be generated for ${account.email}. The current one stops working immediately.`}
          onConfirm={async () => {
            const result = await api.callApi("resetAccountPassword", {
              params: { pk: account.id },
              suppressError: true,
            });

            if (result?.error) return extractErrorMessage(result);
            setTimeout(() => showPassword(account.email, result.password), 0);
            return null;
          }}
        />
      ),
    });
  };

  if (me === null) {
    return (
      <div className="flex justify-center mt-base" data-testid="accounts-loading">
        <Spinner size={32} />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <Typography variant="body" size="medium" data-testid="accounts-forbidden">
        Administrators only.
      </Typography>
    );
  }

  return (
    <div data-testid="accounts-page">
      <div className="flex justify-between items-center mb-base">
        <Typography variant="headline" size="medium">
          Accounts
        </Typography>
        <Button onClick={openCreate} data-testid="accounts-create-button">
          Create account
        </Button>
      </div>

      {loadError && (
        <Typography
          variant="body"
          size="medium"
          className="text-negative-content mb-base"
          data-testid="accounts-load-error"
        >
          {loadError}
        </Typography>
      )}

      {accounts === null ? (
        !loadError && (
          <div className="flex justify-center mt-base">
            <Spinner size={32} />
          </div>
        )
      ) : (
        <table className="w-full text-left" data-testid="accounts-table">
          <thead>
            <tr className="border-b border-neutral-border">
              <th className="p-tight">Name</th>
              <th className="p-tight">Email</th>
              <th className="p-tight">Status</th>
              <th className="p-tight">Roles</th>
              <th className="p-tight">Projects</th>
              <th className="p-tight">Last activity</th>
              <th className="p-tight">Actions</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((account) => {
              const isSelf = account.id === currentUserId;
              const locked = account.is_owner || isSelf;

              return (
                <tr
                  key={account.id}
                  className="border-b border-neutral-border"
                  data-testid={`accounts-row-${account.id}`}
                >
                  <td className="p-tight">{fullName(account) || "—"}</td>
                  <td className="p-tight">{account.email}</td>
                  <td className="p-tight">
                    <Badge
                      variant={account.is_active ? "positive" : "neutral"}
                      data-testid={`accounts-status-${account.id}`}
                    >
                      {account.is_active ? "Active" : "Deactivated"}
                    </Badge>
                  </td>
                  <td className="p-tight">
                    <Space size="tight">
                      {account.is_admin && <Badge variant="info">Admin</Badge>}
                      {account.is_owner && <Badge variant="primary">Owner</Badge>}
                    </Space>
                  </td>
                  <td className="p-tight">{account.project_count}</td>
                  <td className="p-tight">
                    {account.last_activity
                      ? formatDistance(new Date(account.last_activity), new Date(), { addSuffix: true })
                      : "—"}
                  </td>
                  <td className="p-tight">
                    <Space size="tight">
                      <Button
                        size="small"
                        look="outlined"
                        onClick={() => openEdit(account, locked)}
                        data-testid={`accounts-edit-${account.id}`}
                      >
                        Edit
                      </Button>
                      <Button
                        size="small"
                        look="outlined"
                        variant={account.is_active ? "negative" : "primary"}
                        disabled={account.is_active && locked}
                        onClick={() => openToggleActive(account)}
                        data-testid={`accounts-toggle-active-${account.id}`}
                      >
                        {account.is_active ? "Deactivate" : "Reactivate"}
                      </Button>
                      <Button
                        size="small"
                        look="outlined"
                        onClick={() => openResetPassword(account)}
                        data-testid={`accounts-reset-password-${account.id}`}
                      >
                        Reset password
                      </Button>
                    </Space>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
};

AccountsPage.title = "Accounts";
AccountsPage.path = "/accounts";
