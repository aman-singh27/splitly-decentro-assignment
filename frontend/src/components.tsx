import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError, newKey, request } from "./api";
import type { Page, Person } from "./types";
export function Avatar({
  person,
  size = 40,
}: {
  person: Pick<Person, "id" | "name" | "avatar_key">;
  size?: number;
}) {
  const [broken, setBroken] = useState(false);
  const key = /^portrait-(0[1-9]|1[0-6])$/.test(person.avatar_key)
    ? person.avatar_key
    : "portrait-01";
  return (
    <span className="avatar" style={{ width: size, height: size }}>
      {broken ? (
        <span>{person.name.slice(0, 1)}</span>
      ) : (
        <img
          src={`/portraits/${key}.svg`}
          alt=""
          onError={() => setBroken(true)}
          width={size}
          height={size}
        />
      )}
    </span>
  );
}
export function PersonName({ person }: { person: Person }) {
  return (
    <span className="person-name">
      <Avatar person={person} />
      <span>
        {person.name}
        <small>#{person.id}</small>
      </span>
    </span>
  );
}
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error as ApiError;
  return (
    <div role="alert" className="error">
      <strong>{e.message || "Something went wrong. Please retry."}</strong>
      {Object.entries(e.errors ?? {}).map(([field, text]) => (
        <p key={field}>
          {field}: {Array.isArray(text) ? text.join(" ") : text}
        </p>
      ))}
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="empty">
      <div className="empty-art" aria-hidden="true">
        <Avatar
          person={{ id: 1, name: "Friend", avatar_key: "portrait-03" }}
          size={64}
        />
        <span>+</span>
        <Avatar
          person={{ id: 2, name: "Friend", avatar_key: "portrait-08" }}
          size={64}
        />
      </div>
      <h2>{title}</h2>
      <p>{children}</p>
    </section>
  );
}
/** Overlay traps keyboard focus and returns it to the opener on close. */
export function Dialog({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(close);
  closeRef.current = close;
  useEffect(() => {
    const opener = document.activeElement as HTMLElement;
    const el = ref.current!;
    const controls = () =>
      Array.from(
        el.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]",
        ),
      );
    const list = controls();
    (list.find((e) => e.tagName === "INPUT") ?? list[0])?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeRef.current();
      }
      if (e.key === "Tab") {
        const c = controls();
        const first = c[0],
          last = c.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    el.addEventListener("keydown", handler);
    return () => {
      el.removeEventListener("keydown", handler);
      opener?.focus();
    };
  }, []);
  return (
    <div className="overlay">
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
      >
        <header>
          <h2>{title}</h2>
          <button className="icon-button" aria-label="Close" onClick={close}>
            ×
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
export function useResource<T>(path: string, version = 0) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setData(undefined);
    setError(undefined);
    request<T>(path)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, version, refresh]);
  return { data, error, loading, reload: () => setRefresh((n) => n + 1) };
}
/** Append only completed pages; refreshed scopes discard cached pages and late responses. */
export function useList<T>(path: string, version = 0) {
  const [cursor, setCursor] = useState({ path, version, offset: 0 });
  const [items, setItems] = useState<T[]>([]);
  const [data, setData] = useState<Page<T>>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const offset =
    cursor.path === path && cursor.version === version ? cursor.offset : 0;
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(undefined);
    if (offset === 0) {
      setItems([]);
      setData(undefined);
    }
    request<Page<T>>(
      `${path}${path.includes("?") ? "&" : "?"}limit=50&offset=${offset}`,
    )
      .then((page) => {
        if (!active) return;
        setData(page);
        setItems((previous) =>
          offset === 0 ? page.items : [...previous, ...page.items],
        );
      })
      .catch((failure) => {
        if (active) setError(failure);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, version, offset, refresh]);
  return {
    data,
    error,
    loading,
    items,
    more: items.length < (data?.total ?? 0),
    reload: () => setRefresh((value) => value + 1),
    loadMore: () => {
      if (!loading) setCursor({ path, version, offset: items.length });
    },
  };
}
export function More({
  list,
}: {
  list: { more: boolean; loading: boolean; loadMore: () => void };
}) {
  return list.more ? (
    <button
      className="secondary load-more"
      disabled={list.loading}
      onClick={list.loadMore}
    >
      Load more
    </button>
  ) : null;
}
/** Freeze the original payload after a network failure; a retry reuses both payload and key. */
export function useWrite() {
  const operation = useRef<{ path: string; body: unknown; key: string } | null>(
    null,
  );
  const inFlight = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [uncertain, setUncertain] = useState(false);
  async function send<T = any>(path: string, body: unknown) {
    if (inFlight.current) return;
    inFlight.current = true;
    const op = operation.current ?? { path, body, key: newKey() };
    operation.current = op;
    setPending(true);
    setError(undefined);
    try {
      const result = await request<T>(op.path, {
        method: "POST",
        body: op.body,
        key: op.key,
      });
      operation.current = null;
      setUncertain(false);
      return result;
    } catch (e) {
      setError(e);
      if ((e as ApiError).uncertain) setUncertain(true);
      else {
        operation.current = null;
        setUncertain(false);
      }
      throw e;
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }
  return { send, pending, error, uncertain };
}
