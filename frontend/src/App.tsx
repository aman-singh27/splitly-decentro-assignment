import {
  lazy,
  Suspense,
  useEffect,
  useState,
  createContext,
  useContext,
} from "react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { ApiError, request, newKey } from "./api";
import {
  Avatar,
  Dialog,
  Empty,
  ErrorNotice,
  More,
  PersonName,
  useList,
  useResource,
  useWrite,
} from "./components";
import {
  customPreview,
  dateLabel,
  formatMoney,
  parseMoney,
  splitPreview,
  validPhoto,
} from "./domain";
import type {
  Balances,
  Debt,
  Expense,
  Explanation,
  Group,
  Person,
  Workspace,
} from "./types";
const Explorer = lazy(() => import("./Explorer"));
const Context = createContext<{
  workspace: Workspace;
  version: number;
  refresh: () => void;
  setWorkspace: (w: Workspace) => void;
}>(null!);
const useApp = () => useContext(Context);
/** Owns anonymous session scope and the main browser routes. */
export function App() {
  const [workspace, setWorkspace] = useState<Workspace>();
  const [error, setError] = useState<unknown>();
  const [version, setVersion] = useState(0);
  const location = useLocation();
  const refresh = () => setVersion((v) => v + 1);
  useEffect(() => {
    const listener = () => refresh();
    window.addEventListener("focus", listener);
    return () => window.removeEventListener("focus", listener);
  }, []);
  useEffect(() => {
    if (location.pathname === "/join" || workspace) return;
    let active = true;
    request<Workspace>("/workspace")
      .catch((e) => {
        if (e.status === 401)
          return request<Workspace>("/workspace", {
            method: "POST",
            body: {},
            key: newKey(),
          });
        throw e;
      })
      .then((result) => {
        if (active) setWorkspace(result);
      })
      .catch((failure) => {
        if (active) setError(failure);
      });
    return () => {
      active = false;
    };
  }, [location.pathname === "/join"]);
  if (location.pathname === "/join") return <Join onJoin={setWorkspace} />;
  if (!workspace)
    return (
      <main className="startup">
        <a className="brand" href="/">
          Splitly<span>↗</span>
        </a>
        {error ? (
          <>
            <ErrorNotice error={error} />
            <button onClick={() => window.location.reload()}>Retry</button>
          </>
        ) : (
          <p role="status">Opening your groups…</p>
        )}
      </main>
    );
  return (
    <Context.Provider value={{ workspace, version, refresh, setWorkspace }}>
      <div className="shell">
        <aside className="sidebar">
          <Link to="/" className="brand">
            Splitly<span>↗</span>
          </Link>
          <p className="eyebrow nav-label">A little less owing.</p>
          <nav aria-label="Main navigation">
            <NavLink to="/" end>
              <NavigationIcon kind="groups" />
              Groups
            </NavLink>
            <NavLink to="/people">
              <NavigationIcon kind="people" />
              People
            </NavLink>
            <NavLink to="/developers">
              <NavigationIcon kind="code" />
              API docs
            </NavLink>
          </nav>
          <div className="sidebar-note">
            <span className="dot" /> Simple splits.
            <br />
            Good company.
          </div>
        </aside>
        <main className="content">
          <ErrorNotice error={error} />
          {workspace.scope === "group" && (
            <div className="scope-banner">
              <span>Shared group · anyone with the link can contribute</span>
              {workspace.can_switch_to_owner && (
                <button
                  className="text-button"
                  onClick={async () => {
                    try {
                      setWorkspace(
                        await request("/workspace/switch", {
                          method: "POST",
                          body: { scope: "owner" },
                        }),
                      );
                      refresh();
                    } catch (e) {
                      setError(e);
                    }
                  }}
                >
                  Back to my groups
                </button>
              )}
            </div>
          )}
          <Routes>
            <Route path="/" element={<Groups />} />
            <Route path="/people" element={<People />} />
            <Route path="/groups/:id" element={<GroupPage />} />
            <Route path="/groups/:id/expenses/new" element={<ExpenseForm />} />
            <Route path="/developers" element={<Developers />} />
            <Route
              path="*"
              element={
                <>
                  <h1>That page isn’t here.</h1>
                  <Link to="/">Back to Groups</Link>
                </>
              }
            />
          </Routes>
        </main>
      </div>
    </Context.Provider>
  );
}
function PageHead({
  label,
  title,
  description,
  action,
}: {
  label: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        <p className="eyebrow">{label}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}
/** Inline line icons stay sharp at every viewport and do not depend on an icon font. */
function NavigationIcon({ kind }: { kind: "groups" | "people" | "code" }) {
  return (
    <svg
      aria-hidden="true"
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {kind === "groups" ? (
        <>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </>
      ) : kind === "people" ? (
        <>
          <circle cx="9" cy="8" r="3" />
          <path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M21 21v-3a6 6 0 0 0-4-5.6" />
        </>
      ) : (
        <>
          <path d="m8 5-6 7 6 7m8-14 6 7-6 7m-3-17-2 20" />
        </>
      )}
    </svg>
  );
}
/** Lists only groups visible to the current capability; owners may create groups. */
function Groups() {
  const { version, workspace, refresh } = useApp();
  const list = useList<Group>("/groups", version);
  const [create, setCreate] = useState(false);
  return (
    <>
      <PageHead
        label="Keep the good times. Split the costs."
        title="Your groups"
        description="Trips, flatmates, dinner plans. Bring everyone together."
        action={
          workspace.scope === "workspace" && (
            <button className="primary" onClick={() => setCreate(true)}>
              <span aria-hidden="true">＋</span>Create group
            </button>
          )
        }
      />
      <ErrorNotice error={list.error} />
      {list.loading && !list.items.length ? (
        <p role="status">Loading groups…</p>
      ) : list.items.length ? (
        <div className="group-grid">
          {list.items.map((g) => (
            <Link className="group-card" to={`/groups/${g.id}`} key={g.id}>
              <div className="card-top">
                <span className="group-symbol" aria-hidden="true">
                  ↗
                </span>
                <span className="arrow" aria-hidden="true">
                  ↗
                </span>
              </div>
              <h2>{g.name}</h2>
              <p>
                {g.member_count} {g.member_count === 1 ? "member" : "members"} ·{" "}
                {g.expense_count}{" "}
                {g.expense_count === 1 ? "expense" : "expenses"}
              </p>
              <div className="avatar-stack">
                {g.member_preview.map((p) => (
                  <Avatar person={p} key={p.id} size={36} />
                ))}
                {g.member_count > 4 && <span>+{g.member_count - 4}</span>}
              </div>
              <footer>
                <span>Total shared</span>
                <strong>{formatMoney(g.total_expense_minor)}</strong>
              </footer>
            </Link>
          ))}
        </div>
      ) : (
        <Empty title="Good company starts here.">
          Create a group, add your people, then share your first expense.
        </Empty>
      )}
      <More list={list} />
      <div className="quiet-note">
        <span aria-hidden="true">✳</span> Every balance has a story. See
        exactly what adds up.
      </div>
      {create && <CreateGroup close={() => setCreate(false)} done={refresh} />}
    </>
  );
}
/** Creates a group once and opens its member setup. */
function CreateGroup({ close, done }: { close: () => void; done: () => void }) {
  const [name, setName] = useState("");
  const write = useWrite();
  const navigate = useNavigate();
  return (
    <Dialog title="Create group" close={close}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            const g = await write.send<Group>("/groups", { name: name.trim() });
            if (g) {
              done();
              close();
              navigate(`/groups/${g.id}?tab=members`);
            }
          } catch {}
        }}
      >
        <p>A name everyone recognises. You can add members next.</p>
        <label>
          Group name
          <input
            autoComplete="off"
            maxLength={80}
            required
            value={name}
            disabled={write.uncertain}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <ErrorNotice error={write.error} />
        <div className="form-actions">
          <button type="button" className="secondary" onClick={close}>
            Cancel
          </button>
          <button className="primary" disabled={write.pending}>
            {write.pending
              ? "Creating…"
              : write.uncertain
                ? "Retry same request"
                : "Create group"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
/** Lists available people without conflating repeated display names. */
function People() {
  const { version, refresh, workspace } = useApp();
  const list = useList<Person>("/users", version);
  const [create, setCreate] = useState(false);
  return (
    <>
      <PageHead
        label="Familiar faces"
        title="People"
        description={
          workspace.scope === "group"
            ? "People available in this shared group."
            : "Everyone in your workspace. Names are self-declared; no sign-in needed."
        }
        action={
          <button className="primary" onClick={() => setCreate(true)}>
            <span aria-hidden="true">＋</span>Add person
          </button>
        }
      />
      <ErrorNotice error={list.error} />
      {list.loading && !list.items.length ? (
        <p role="status">Loading people…</p>
      ) : list.items.length ? (
        <section className="people-grid">
          {list.items.map((p) => (
            <article className="person-card" key={p.id}>
              <Avatar person={p} size={64} />
              <div>
                <h2>{p.name}</h2>
                <p>
                  #{p.id}
                  {p.group_count !== undefined
                    ? ` · ${p.group_count} groups`
                    : ""}
                </p>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <Empty title="Meet your people.">
          Add a person here, or create and add them inside a group.
        </Empty>
      )}
      <More list={list} />
      {create && <AddPerson close={() => setCreate(false)} done={refresh} />}
    </>
  );
}
/** Creates a person independently of group membership. */
function AddPerson({ close, done }: { close: () => void; done: () => void }) {
  const [name, setName] = useState("");
  const write = useWrite();
  return (
    <Dialog title="Add person" close={close}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await write.send("/users", { name: name.trim() });
            done();
            close();
          } catch {}
        }}
      >
        <label>
          Name
          <input
            value={name}
            required
            maxLength={80}
            disabled={write.uncertain}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <p className="helper">
          Names can repeat. Every person gets a unique ID and a familiar face.
        </p>
        <ErrorNotice error={write.error} />
        <button className="primary full" disabled={write.pending}>
          {write.pending
            ? "Adding…"
            : write.uncertain
              ? "Retry same request"
              : "Add person"}
        </button>
      </form>
    </Dialog>
  );
}
/** Separates person creation from membership so failed adds can be retried safely. */
function AddMembers({
  id,
  members,
  close,
}: {
  id: number;
  members: Person[];
  close: () => void;
}) {
  const { version, refresh } = useApp();
  const people = useList<Person>("/users", version);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<Person>();
  const [addTarget, setAddTarget] = useState<Person>();
  const create = useWrite();
  const add = useWrite();
  const busy = create.pending || add.pending;
  async function addExisting(p: Person) {
    setAddTarget(p);
    try {
      await add.send(`/groups/${id}/members`, { user_id: p.id });
      refresh();
      close();
    } catch {}
  }
  return (
    <Dialog title="Add members" close={close}>
      <p>
        New members join future expenses. Earlier shares stay exactly as saved.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            const p =
              created ??
              (await create.send<Person>("/users", { name: name.trim() }));
            if (p) {
              setCreated(p);
              await addExisting(p);
            }
          } catch {}
        }}
      >
        <label>
          Name
          <input
            required
            maxLength={80}
            value={name}
            disabled={!!created || create.uncertain || add.uncertain}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        {created && !!add.error && (
          <p className="helper">
            Person created; adding to group failed. Retry adding.
          </p>
        )}
        <ErrorNotice error={create.error || add.error} />
        <button className="primary full" disabled={busy || add.uncertain}>
          {busy
            ? "Adding…"
            : created
              ? "Retry adding"
              : create.uncertain
                ? "Retry same request"
                : "Create and add person"}
        </button>
      </form>
      {add.uncertain && addTarget && (
        <div className="retry-member">
          <p className="helper">
            The result of adding {addTarget.name} is unknown. Confirm that same
            request before adding anyone else.
          </p>
          <button
            className="primary full"
            disabled={busy}
            onClick={() => addExisting(addTarget)}
          >
            {busy ? "Checking…" : `Retry adding ${addTarget.name}`}
          </button>
        </div>
      )}
      <div className="divider-label">Or add someone already here</div>
      <ErrorNotice error={people.error} />
      <div className="directory-list">
        {people.items.map((p) => (
          <div className="person-row" key={p.id}>
            <PersonName person={p} />
            {members.some((m) => m.id === p.id) ? (
              <small>Already a member</small>
            ) : (
              <button
                className="secondary"
                disabled={
                  busy || !!created || create.uncertain || add.uncertain
                }
                onClick={() => addExisting(p)}
                aria-label={`Add ${p.name}`}
              >
                Add
              </button>
            )}
          </div>
        ))}
      </div>
      <More list={people} />
    </Dialog>
  );
}
/** Deep-linked group workspace with expenses, balances and member tabs. */
function GroupPage() {
  const id = Number(useParams().id);
  const { version } = useApp();
  const group = useResource<Group>(`/groups/${id}`, version);
  const members = useList<Person>(`/groups/${id}/members`, version);
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "expenses";
  const [adding, setAdding] = useState(false);
  const [share, setShare] = useState(false);
  if (group.error)
    return (
      <>
        <ErrorNotice error={group.error} />
        <Link to="/">Back to Groups</Link>
      </>
    );
  if (!group.data) return <p role="status">Loading group…</p>;
  const g = group.data;
  return (
    <>
      <Link to="/" className="back-link">
        ← Groups
      </Link>
      <PageHead
        label="Shared expenses. Clear balances."
        title={g.name}
        description={`${g.member_count} ${g.member_count === 1 ? "member" : "members"} · ${g.expense_count} ${g.expense_count === 1 ? "expense" : "expenses"}`}
        action={
          <div className="head-actions">
            <button className="secondary" onClick={() => setShare(true)}>
              Share group
            </button>
            {g.member_count > 0 ? (
              <Link className="primary" to={`/groups/${id}/expenses/new`}>
                <span aria-hidden="true">＋</span>Add expense
              </Link>
            ) : (
              <button className="primary" onClick={() => setAdding(true)}>
                Add members
              </button>
            )}
          </div>
        }
      />
      <section className="group-overview">
        <div>
          <p>Total shared</p>
          <strong>{formatMoney(g.total_expense_minor)}</strong>
          <small>All recorded expenses</small>
        </div>
        <div className="overview-people">
          {members.items.slice(0, 5).map((p) => (
            <Avatar key={p.id} person={p} size={48} />
          ))}
          <span>
            {g.member_count > 5 ? `+${g.member_count - 5}` : "In good company."}
          </span>
        </div>
      </section>
      <div className="tabs" role="tablist" aria-label="Group sections">
        {["expenses", "balances", "members"].map((t) => (
          <button
            role="tab"
            aria-selected={tab === t}
            key={t}
            onClick={() => setParams({ tab: t })}
          >
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === "balances" ? (
        <BalanceView id={id} />
      ) : tab === "members" ? (
        <section role="tabpanel">
          <div className="section-head">
            <div>
              <h2>The people in this group</h2>
              <p>Everyone shares future expenses by default.</p>
            </div>
            {g.member_count > 0 && (
              <button className="secondary" onClick={() => setAdding(true)}>
                Add members
              </button>
            )}
          </div>
          <ErrorNotice error={members.error} />
          {members.items.length ? (
            <div className="people-grid">
              {members.items.map((p) => (
                <article className="person-card" key={p.id}>
                  <Avatar person={p} size={64} />
                  <div>
                    <h3>{p.name}</h3>
                    <small>#{p.id}</small>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty title="Add your first member.">
              You need at least one member before adding an expense.
            </Empty>
          )}
          <More list={members} />
        </section>
      ) : (
        <Expenses id={id} />
      )}{" "}
      {adding && (
        <AddMembers
          id={id}
          members={members.items}
          close={() => setAdding(false)}
        />
      )}{" "}
      {share && <Share id={id} close={() => setShare(false)} />}
    </>
  );
}
/** Exposes a group capability link; never the workspace owner key. */
function Share({ id, close }: { id: number; close: () => void }) {
  const invite = useResource<{ url: string }>(`/groups/${id}/invite`);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<unknown>();
  const url = invite.data
    ? new URL(invite.data.url, window.location.origin).href
    : "";
  return (
    <Dialog title="Share group" close={close}>
      <p>
        Anyone with this link can view this group, add members and record
        expenses or payments. Keep it with your group.
      </p>
      <ErrorNotice error={invite.error || error} />
      {url && (
        <>
          <label>
            Group link
            <input
              readOnly
              value={url}
              data-testid="share-url"
              onFocus={(e) => e.target.select()}
            />
          </label>
          <button
            className="primary full"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(url);
                setCopied(true);
              } catch {
                setError(new Error("Select and copy the group link above."));
              }
            }}
          >
            {copied ? "Link copied" : "Copy link"}
          </button>
        </>
      )}
    </Dialog>
  );
}
/** Renders immutable saved shares and capability-protected receipt photos. */
function Expenses({ id }: { id: number }) {
  const { version } = useApp();
  const expenses = useList<Expense>(`/groups/${id}/expenses`, version);
  return (
    <section role="tabpanel">
      <div className="section-head">
        <h2>Expense history</h2>
        <p>Saved shares. Nothing recalculated behind your back.</p>
      </div>
      <ErrorNotice error={expenses.error} />
      {expenses.loading && !expenses.items.length ? (
        <p role="status">Loading expenses…</p>
      ) : expenses.items.length ? (
        <div className="expense-list">
          {expenses.items.map((e) => (
            <details className="expense" key={e.id} data-testid="expense-row">
              <summary>
                <div className="expense-symbol" aria-hidden="true">
                  ↗
                </div>
                <div className="expense-title">
                  <strong>{e.description}</strong>
                  <span>
                    {e.paid_by.name} paid · {dateLabel(e.created_at)} ·{" "}
                    {e.participant_count} people
                  </span>
                </div>
                <strong>{formatMoney(e.amount_minor)}</strong>
                <span aria-hidden="true">⌄</span>
              </summary>
              <div className="receipt" data-testid="expense-receipt">
                <p className="eyebrow">
                  Saved receipt · #{e.id} ·{" "}
                  {e.split_type === "custom" ? "Custom amounts" : "Equal split"}
                </p>
                {e.shares.map((p) => (
                  <div className="receipt-row" key={p.user_id}>
                    <PersonName
                      person={{
                        id: p.user_id,
                        name: p.name,
                        avatar_key: p.avatar_key,
                      }}
                    />
                    <strong>{formatMoney(p.amount_minor)}</strong>
                  </div>
                ))}
                <p className="helper">
                  These shares keep the members and amounts from when this
                  expense was added.
                </p>
                {e.receipt_url && (
                  <details className="photo-details">
                    <summary>View bill photo</summary>
                    <a href={e.receipt_url} target="_blank" rel="noreferrer">
                      <img
                        className="bill-photo"
                        src={e.receipt_url}
                        alt="Bill photo"
                      />
                    </a>
                  </details>
                )}
              </div>
            </details>
          ))}
        </div>
      ) : (
        <Empty title="The first one’s on someone.">
          Add an expense to keep track of who paid and what everyone shares.
        </Empty>
      )}
      <More list={expenses} />
    </section>
  );
}
/** Shows direct pair debts, member positions and explanations, including settled pairs. */
function BalanceView({ id }: { id: number }) {
  const { version } = useApp();
  const result = useResource<Balances>(`/groups/${id}/balances`, version);
  const [explain, setExplain] = useState<[number, number]>();
  const [payment, setPayment] = useState<Debt>();
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const lookup = (uid: number) =>
    result.data!.members.find((p) => p.user_id === uid)!;
  return (
    <section role="tabpanel">
      <div className="section-head">
        <div>
          <h2>Who owes whom</h2>
          <p>
            Direct balances, after opposite expenses and recorded payments
            cancel out.
          </p>
        </div>
      </div>
      <ErrorNotice error={result.error} />
      {result.loading ? (
        <p role="status">Calculating balances…</p>
      ) : (
        result.data && (
          <>
            {result.data.debts.length ? (
              <div className="debt-list">
                {result.data.debts.map((d) => (
                  <article
                    className="debt-row"
                    data-testid="debt-row"
                    key={`${d.from_user_id}-${d.to_user_id}`}
                  >
                    <div>
                      <span className="debt-people">
                        <Avatar
                          person={{
                            ...lookup(d.from_user_id),
                            id: d.from_user_id,
                          }}
                        />
                        <strong>{lookup(d.from_user_id).name}</strong>
                        <span>owes</span>
                        <strong>{lookup(d.to_user_id).name}</strong>
                      </span>
                      <strong className="debt-amount">
                        {formatMoney(d.amount_minor)}
                      </strong>
                    </div>
                    <div className="debt-actions">
                      <button
                        className="text-button"
                        onClick={() =>
                          setExplain([d.to_user_id, d.from_user_id])
                        }
                      >
                        Why this amount?
                      </button>
                      <button
                        className="secondary"
                        onClick={() => setPayment(d)}
                      >
                        Record payment
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="settled">
                <span aria-hidden="true">✓</span>
                <h3>All square.</h3>
                <p>
                  No direct debts remain. Earlier contributions are still here
                  to explain.
                </p>
              </div>
            )}
            <div className="section-head">
              <h2>Everyone’s position</h2>
            </div>
            <div className="position-grid">
              {result.data.members.map((m) => (
                <article className="position" key={m.user_id}>
                  <PersonName person={{ id: m.user_id, ...m }} />
                  <dl>
                    <div>
                      <dt>Paid for expenses</dt>
                      <dd>{formatMoney(m.paid_minor)}</dd>
                    </div>
                    <div>
                      <dt>Allocated share</dt>
                      <dd>{formatMoney(m.allocated_minor)}</dd>
                    </div>
                    <div>
                      <dt>Owes</dt>
                      <dd>{formatMoney(m.owes_minor)}</dd>
                    </div>
                    <div>
                      <dt>Receivable</dt>
                      <dd>{formatMoney(m.receivable_minor)}</dd>
                    </div>
                    <div className="net">
                      <dt>Net position</dt>
                      <dd>{formatMoney(m.net_minor)}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
            {result.data.members.length >= 2 && (
              <section className="pair-panel">
                <h3>Every balance has a story.</h3>
                <p>
                  Choose two people to understand their history, even after they
                  settle up.
                </p>
                <div className="pair-select">
                  <label>
                    First person
                    <select value={a} onChange={(e) => setA(e.target.value)}>
                      <option value="">Choose person</option>
                      {result.data.members.map((m) => (
                        <option key={m.user_id} value={m.user_id}>
                          {m.name} · #{m.user_id}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Second person
                    <select value={b} onChange={(e) => setB(e.target.value)}>
                      <option value="">Choose person</option>
                      {result.data.members
                        .filter((m) => String(m.user_id) !== a)
                        .map((m) => (
                          <option key={m.user_id} value={m.user_id}>
                            {m.name} · #{m.user_id}
                          </option>
                        ))}
                    </select>
                  </label>
                  <button
                    className="secondary"
                    disabled={!a || !b || a === b}
                    onClick={() => setExplain([Number(a), Number(b)])}
                  >
                    Why this amount?
                  </button>
                </div>
              </section>
            )}
          </>
        )
      )}
      {explain && (
        <Explain id={id} pair={explain} close={() => setExplain(undefined)} />
      )}{" "}
      {payment && (
        <Payment
          id={id}
          debt={payment}
          from={lookup(payment.from_user_id).name}
          to={lookup(payment.to_user_id).name}
          close={() => setPayment(undefined)}
        />
      )}
    </section>
  );
}
/** Displays signed ledger contributions and the authoritative full pair total. */
function Explain({
  id,
  pair,
  close,
}: {
  id: number;
  pair: [number, number];
  close: () => void;
}) {
  const { version } = useApp();
  const result = useResource<Explanation>(
    `/groups/${id}/balances/explanation?user_a_id=${pair[0]}&user_b_id=${pair[1]}`,
    version,
  );
  return (
    <Dialog title="Why this amount?" close={close}>
      <p>
        Positive contributions mean the second person owes the first. Negative
        contributions reduce that balance.
      </p>
      <ErrorNotice error={result.error} />
      {result.data && (
        <>
          <div className="explanation-total">
            <span>Current direct balance</span>
            <strong>{formatMoney(result.data.amount_minor)}</strong>
          </div>
          {result.data.items.length ? (
            result.data.items.map((item, i) => (
              <div
                className="contribution"
                key={`${item.type}-${item.record_id}-${i}`}
              >
                <div>
                  <strong>{item.description || "Recorded payment"}</strong>
                  <small>
                    {item.type} · {dateLabel(item.created_at)}
                  </small>
                </div>
                <strong>
                  {item.contribution_minor >= 0 ? "+" : "−"}
                  {formatMoney(Math.abs(item.contribution_minor))}
                </strong>
              </div>
            ))
          ) : (
            <p>No contributions between these people yet.</p>
          )}
          <p className="helper">
            Full pair total includes all {result.data.total} records. Each
            contribution uses the saved paise amount.
          </p>
          {result.data.total > result.data.items.length && (
            <a
              href={`/api/v1/groups/${id}/balances/explanation?user_a_id=${pair[0]}&user_b_id=${pair[1]}&limit=100`}
              target="_blank"
              rel="noreferrer"
            >
              View all explanation records
            </a>
          )}
        </>
      )}
    </Dialog>
  );
}
/** Records external partial/full payments and retains uncertain request keys. */
function Payment({
  id,
  debt,
  from,
  to,
  close,
}: {
  id: number;
  debt: Debt;
  from: string;
  to: string;
  close: () => void;
}) {
  const { refresh } = useApp();
  const [amount, setAmount] = useState(debt.amount);
  const [validation, setValidation] = useState<unknown>();
  const write = useWrite();
  return (
    <Dialog title="Record payment" close={close}>
      <p>
        <strong>{from}</strong> paid <strong>{to}</strong> outside Splitly. This
        records that payment; it does not transfer money.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const minor = parseMoney(amount);
          if (minor === null || minor > debt.amount_minor) {
            setValidation(
              new Error(
                "Enter a positive amount no greater than the current direct debt.",
              ),
            );
            return;
          }
          setValidation(undefined);
          try {
            await write.send("/settlements", {
              group_id: id,
              from_user_id: debt.from_user_id,
              to_user_id: debt.to_user_id,
              amount,
            });
            refresh();
            close();
          } catch {}
        }}
      >
        <label>
          Amount in INR
          <input
            inputMode="decimal"
            value={amount}
            disabled={write.uncertain}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <p className="helper">
          Current direct debt: {formatMoney(debt.amount_minor)}. Partial
          payments are welcome.
        </p>
        <ErrorNotice error={validation || write.error} />
        <button className="primary full" disabled={write.pending}>
          {write.pending
            ? "Recording…"
            : write.uncertain
              ? "Retry same request"
              : "Record payment"}
        </button>
      </form>
    </Dialog>
  );
}
/** Previews equal/custom allocations; commits the expense before an optional photo upload. */
function ExpenseForm() {
  const id = Number(useParams().id);
  const { version, refresh } = useApp();
  const group = useResource<Group>(`/groups/${id}`, version);
  const roster = useList<Person>(`/groups/${id}/members`, version);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [payer, setPayer] = useState("");
  const [custom, setCustom] = useState(false);
  const [shares, setShares] = useState<Record<number, string>>({});
  const [photo, setPhoto] = useState<File>();
  const [preview, setPreview] = useState("");
  const [validation, setValidation] = useState<unknown>();
  const [saved, setSaved] = useState<Expense>();
  const write = useWrite();
  const upload = useWrite();
  const navigate = useNavigate();
  useEffect(() => {
    if (roster.items.length === 1) setPayer(String(roster.items[0].id));
  }, [roster.items]);
  useEffect(() => {
    if (!photo) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(photo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);
  const equal = splitPreview(amount, roster.items);
  const customSplit = customPreview(amount, roster.items, shares);
  const finish = () => {
    refresh();
    navigate(`/groups/${id}?tab=expenses`);
  };
  async function attach(expense: Expense) {
    if (!photo) {
      finish();
      return;
    }
    const form = new FormData();
    form.append("photo", photo);
    try {
      await upload.send(`/expenses/${expense.id}/receipt`, form);
      finish();
    } catch {}
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (saved) {
      await attach(saved);
      return;
    }
    if (parseMoney(amount) === null) {
      setValidation(
        new Error(
          "Enter a positive INR amount, with at most two decimal places.",
        ),
      );
      return;
    }
    if (!payer) {
      setValidation(new Error("Choose who paid. Names are self-declared."));
      return;
    }
    if (custom && !customSplit.valid) {
      setValidation(
        new Error(
          "Custom shares must include every member and add up exactly to the expense amount. Zero is allowed.",
        ),
      );
      return;
    }
    setValidation(undefined);
    try {
      const body = {
        group_id: id,
        paid_by: Number(payer),
        amount,
        description,
        ...(custom
          ? {
              split_type: "custom",
              splits: roster.items.map((p) => ({
                user_id: p.id,
                amount: shares[p.id],
              })),
            }
          : {}),
      };
      const expense = await write.send<Expense>("/expenses", body);
      if (expense) {
        setSaved(expense);
        await attach(expense);
      }
    } catch {}
  }
  return (
    <>
      <Link className="back-link" to={`/groups/${id}`}>
        ← {group.data?.name ?? "Group"}
      </Link>
      <PageHead
        label="One shared moment"
        title="Add an expense"
        description="Say what it was, who paid, and how you’re sharing it."
      />
      <ErrorNotice error={group.error || roster.error} />
      {roster.loading && !roster.items.length ? (
        <p role="status">Loading members…</p>
      ) : !roster.items.length ? (
        <Empty title="A group needs its people first.">
          <Link to={`/groups/${id}?tab=members`}>Add members</Link> before
          recording an expense.
        </Empty>
      ) : (
        <form className="expense-form" onSubmit={submit}>
          <div className="form-main">
            <fieldset disabled={write.uncertain || !!saved}>
              <label>
                What was it for?
                <textarea
                  required
                  maxLength={200}
                  placeholder="Dinner, groceries, the weekend away…"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </label>
              <div className="form-two">
                <label>
                  Amount in INR
                  <input
                    inputMode="decimal"
                    placeholder="0.00"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                  />
                </label>
                <label>
                  Paid by
                  <select
                    required
                    value={payer}
                    onChange={(e) => setPayer(e.target.value)}
                  >
                    <option value="">Choose who paid</option>
                    {roster.items.map((p) => (
                      <option key={p.id} value={p.id}>
                        {roster.items.filter((o) => o.name === p.name).length >
                        1
                          ? `${p.name} · #${p.id}`
                          : p.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="split-control" aria-label="Split type">
                <button
                  type="button"
                  aria-pressed={!custom}
                  onClick={() => setCustom(false)}
                >
                  Equal
                </button>
                <button
                  type="button"
                  aria-pressed={custom}
                  onClick={() => setCustom(true)}
                >
                  Custom amounts
                </button>
              </div>
              <h2>
                {custom
                  ? "Set each person’s share"
                  : "Split equally among all members"}
              </h2>
              <p className="helper">
                All {roster.items.length} current group members are included.
                {custom
                  ? " A share can be zero."
                  : " Any extra paise go in member ID order."}
              </p>
              <div className="split-roster">
                {roster.items.map((p) => (
                  <div className="split-person" key={p.id}>
                    <PersonName person={p} />
                    {custom ? (
                      <label className="custom-share">
                        Share for {p.name}
                        <input
                          inputMode="decimal"
                          value={shares[p.id] ?? ""}
                          placeholder="0.00"
                          onChange={(e) =>
                            setShares({ ...shares, [p.id]: e.target.value })
                          }
                        />
                      </label>
                    ) : (
                      <strong>
                        {equal.find((s) => s.id === p.id)
                          ? formatMoney(equal.find((s) => s.id === p.id)!.minor)
                          : "—"}
                      </strong>
                    )}
                  </div>
                ))}
              </div>
              {custom && (
                <p className="allocation">
                  Allocated {formatMoney(customSplit.total)} · Remaining{" "}
                  {formatMoney(customSplit.remaining)}
                </p>
              )}
              <label className="upload">
                Bill photo (optional)
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      const error = validPhoto(file);
                      if (error) {
                        setValidation(new Error(error));
                        return;
                      }
                    }
                    setPhoto(file);
                    setValidation(undefined);
                  }}
                />
                <span>
                  JPEG, PNG or WebP · up to 5 MB. A reference photo, no
                  scanning.
                </span>
              </label>
              {preview && (
                <img
                  className="photo-preview"
                  src={preview}
                  alt="Selected bill photo"
                />
              )}
            </fieldset>
          </div>
          <aside className="expense-summary">
            <p className="eyebrow">Ready to share</p>
            <strong className="summary-amount">
              {formatMoney(parseMoney(amount) ?? 0)}
            </strong>
            <p>
              {custom ? "Custom shares" : "Equal shares"} ·{" "}
              {roster.items.length} people
            </p>
            <hr />
            <p className="helper">
              Shares are saved as a snapshot. Adding members later won’t change
              this expense.
            </p>
            <ErrorNotice error={validation || write.error} />
            {saved && !!upload.error && (
              <>
                <p role="status">Expense saved. Photo upload failed.</p>
                <ErrorNotice error={upload.error} />
              </>
            )}
            <button
              className="primary full"
              disabled={
                write.pending ||
                upload.pending ||
                roster.more ||
                roster.loading ||
                !!roster.error ||
                group.loading ||
                !!group.error
              }
            >
              {write.pending
                ? "Saving…"
                : upload.pending
                  ? "Uploading…"
                  : saved
                    ? "Retry photo upload"
                    : write.uncertain
                      ? "Retry same request"
                      : "Add expense"}
            </button>
            {saved && !!upload.error && (
              <button
                type="button"
                className="text-button full"
                onClick={finish}
              >
                Continue without photo
              </button>
            )}
            {roster.more && (
              <>
                <p className="helper">
                  Load all members before previewing the split.
                </p>
                <More list={roster} />
              </>
            )}
          </aside>
        </form>
      )}
    </>
  );
}
/** Provides the public API quickstart, exports and locally bundled explorer. */
function Developers() {
  return (
    <>
      <PageHead
        label="Build something together"
        title="API documentation"
        description="The same API behind Splitly. Try it here or take it to Postman."
      />
      <div className="docs-downloads">
        <a className="primary" href="/api/postman.json" download>
          Postman collection
        </a>
        <a className="secondary" href="/api/environment.json" download>
          Postman environment
        </a>
        <a className="secondary" href="/api/openapi.json" download>
          OpenAPI
        </a>
      </div>
      <section className="api-intro">
        <h2>A three-person dinner, from start to finish.</h2>
        <ol>
          <li>
            GET <code>/api/v1/workspace</code> to establish CSRF; POST it if
            your session is new.
          </li>
          <li>
            Create Mohit, Rahul and Ankit through <code>POST /users</code>.
            Create a group, then add each user through its members endpoint.
          </li>
          <li>
            POST an expense: Mohit paid ₹1,200. Equal sharing gives each person
            ₹400; Rahul and Ankit each owe Mohit ₹400.
          </li>
          <li>
            Read balances and pair explanations. Record an outside payment
            through settlements.
          </li>
        </ol>
        <p>
          Use <code>Idempotency-Key</code> for expenses, settlements and bill
          uploads. Retrying with the same key and payload checks the original
          result. Send decimal INR amounts; the server stores integer paise.
        </p>
        <p>
          The explorer uses your current session. Postman accepts{" "}
          <code>X-Workspace-Key</code> or <code>X-Group-Key</code>. Group keys
          grant only that group. Downloads contain placeholders, never your
          private keys.
        </p>
        <p>
          Equal is the default. Custom amounts must include every current
          member, allow zero and sum exactly to the total. Photos are optional
          protected JPEG, PNG or WebP attachments.
        </p>
      </section>
      <Suspense fallback={<p role="status">Loading API explorer…</p>}>
        <Explorer />
      </Suspense>
    </>
  );
}
/** Exchanges a fragment capability for session access before entering the group. */
function Join({ onJoin }: { onJoin: (w: Workspace) => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [error, setError] = useState<unknown>();
  const [pending, setPending] = useState(true);
  useEffect(() => {
    const key = new URLSearchParams(location.hash.slice(1)).get("key");
    if (!key) {
      setError(new Error("This group link is incomplete. Ask for a new link."));
      setPending(false);
      return;
    }
    request("/workspace")
      .catch(() => undefined)
      .then(() =>
        request<Workspace>("/workspace/join", {
          method: "POST",
          body: { access_key: key },
        }),
      )
      .then((w) => {
        onJoin(w);
        navigate(w.group_id ? `/groups/${w.group_id}` : "/", { replace: true });
      })
      .catch(setError)
      .finally(() => setPending(false));
  }, [location.hash]);
  return (
    <main className="startup">
      <Link to="/" className="brand">
        Splitly<span>↗</span>
      </Link>
      <h1>{pending ? "Joining your group…" : "That link didn’t work."}</h1>
      <ErrorNotice error={error} />
      {!pending && (
        <Link className="secondary" to="/">
          Back to Groups
        </Link>
      )}
    </main>
  );
}
