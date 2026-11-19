import { SidebarMenu } from "../../components/SidebarMenu/SidebarMenu";
import { useRbacMe } from "../../hooks/useRbacMe";
import { AccountsPage } from "./AccountsPage/AccountsPage";
import { PeoplePage } from "./PeoplePage/PeoplePage";
import { WebhookPage } from "../WebhookPage/WebhookPage";

const ALLOW_ORGANIZATION_WEBHOOKS = window.APP_SETTINGS.flags?.allow_organization_webhooks;

const MenuLayout = ({ children, ...routeProps }) => {
  const isAdmin = useRbacMe()?.is_admin === true;
  const menuItems = [PeoplePage];

  if (isAdmin) {
    menuItems.push(AccountsPage);
  }

  if (ALLOW_ORGANIZATION_WEBHOOKS) {
    menuItems.push(WebhookPage);
  }
  return <SidebarMenu menuItems={menuItems} path={routeProps.match.url} children={children} />;
};

const organizationPages = {};

organizationPages.AccountsPage = AccountsPage;

if (ALLOW_ORGANIZATION_WEBHOOKS) {
  organizationPages[WebhookPage] = WebhookPage;
}

export const OrganizationPage = {
  title: "Organization",
  path: "/organization",
  exact: true,
  layout: MenuLayout,
  component: PeoplePage,
  pages: organizationPages,
};
