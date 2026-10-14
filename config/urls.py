from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, re_path
from drf_spectacular.views import SpectacularSwaggerView

from config import http
from ledger import artifacts, views
from ledger.receipts import ReceiptView


def api(route, view):
    return re_path(r"^api/v1/" + route + r"/?$", view.as_view())


urlpatterns = [
    api("workspace", views.WorkspaceView),
    api("workspace/join", views.JoinView),
    api("workspace/switch", views.SwitchView),
    api("workspace/invite", views.WorkspaceInviteView),
    api("users", views.UsersView),
    api("groups", views.GroupsView),
    api(r"groups/(?P<group_id>\d+)", views.GroupView),
    api(r"groups/(?P<group_id>\d+)/members", views.MembersView),
    api("expenses", views.ExpensesView),
    api(r"expenses/(?P<expense_id>\d+)/receipt", ReceiptView),
    api(r"groups/(?P<group_id>\d+)/expenses", views.ExpenseHistoryView),
    api("balances", views.BalancesView),
    api(r"groups/(?P<group_id>\d+)/balances", views.BalancesView),
    api(r"groups/(?P<group_id>\d+)/balances/explanation", views.ExplanationView),
    api("settlements", views.SettlementsView),
    api(r"groups/(?P<group_id>\d+)/settlements", views.SettlementHistoryView),
    api(r"groups/(?P<group_id>\d+)/invite", views.GroupInviteView),
    path("api/openapi.json", artifacts.schema_download, name="openapi"),
    path("api/postman.json", artifacts.postman_download),
    path("api/environment.json", artifacts.environment_download),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="openapi"), name="swagger"),
    path("health/live", http.live),
    path("health/ready", http.ready),
    re_path(r"^api/(?P<path>.*)$", http.missing_api),
    re_path(r"^media/(?P<path>.*)$", http.missing_api),
]
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
urlpatterns += [re_path(r"^(?P<path>.*)$", http.spa)]
