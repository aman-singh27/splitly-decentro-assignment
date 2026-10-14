import { useEffect, useRef } from "react";
import SwaggerUI from "swagger-ui-dist/swagger-ui-bundle.js";
import "swagger-ui-dist/swagger-ui.css";
/** Swagger is bundled locally; API exploration shares the current scoped session. */
export default function Explorer() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const ui = SwaggerUI({
      url: "/api/openapi.json",
      domNode: ref.current,
      deepLinking: false,
      validatorUrl: null,
      requestInterceptor: (req: {
        headers: Record<string, string>;
        credentials: string;
      }) => {
        req.credentials = "same-origin";
        const csrf = document.cookie
          .split("; ")
          .find((c) => c.startsWith("csrftoken="))
          ?.split("=")[1];
        if (csrf) req.headers["X-CSRFToken"] = decodeURIComponent(csrf);
        return req;
      },
    });
    return () => ui.getSystem?.().fn?.clear?.();
  }, []);
  return <div ref={ref} className="explorer" />;
}
