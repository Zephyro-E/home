// Componentes Alpine.js de la aplicación. Se carga antes que Alpine (ambos con defer).

document.addEventListener("alpine:init", () => {
  // Selector de tema: Sistema → Claro → Oscuro. Se guarda en el navegador y, con sesión, en el perfil.
  Alpine.data("themeSwitcher", () => ({
    pref: document.documentElement.dataset.themePref || "system",

    labels: {},

    init() {
      // En init, $el es el propio botón, que guarda los textos traducidos en data-label-*.
      const d = this.$el.dataset;
      this.labels = { system: d.labelSystem, light: d.labelLight, dark: d.labelDark };
      window
        .matchMedia("(prefers-color-scheme: dark)")
        .addEventListener("change", () => this.apply());
    },

    get label() {
      return this.labels[this.pref];
    },

    cycle() {
      this.pref = { system: "light", light: "dark", dark: "system" }[this.pref];
      try {
        localStorage.setItem("theme", this.pref);
      } catch (e) {
        /* almacenamiento no disponible: el cambio dura hasta recargar */
      }
      this.apply();
      this.save();
    },

    // Con sesión iniciada, guarda la preferencia en el perfil (la URL la pone base.html).
    save() {
      const url = document.body.dataset.themeUrl;
      const token = document.querySelector("[name=csrfmiddlewaretoken]")?.value || this.csrf();
      if (!url || !token) return;
      fetch(url, {
        method: "POST",
        headers: { "X-CSRFToken": token, "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ theme: this.pref }),
      }).catch(() => {});
    },

    csrf() {
      const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
      return m ? decodeURIComponent(m[1]) : "";
    },

    apply() {
      const dark =
        this.pref === "dark" ||
        (this.pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.dataset.theme = dark ? "dark" : "light";
      document.documentElement.dataset.themePref = this.pref;
    },
  }));

  // --- Borrar con "Deshacer" (ADR-010) -------------------------------------------------
  // El elemento se oculta al momento y aparece un aviso durante unos segundos. Si no se
  // deshace, se envía el borrado definitivo al servidor. Si se sale de la página antes,
  // el borrado se envía al salir (keepalive); si la pestaña se cierra de golpe y el envío
  // no llega, el elemento simplemente sigue existiendo.
  Alpine.store("undo", {
    visible: false,
    message: "",
    pending: null,
    seconds: 6,

    start({ message, commit, restore }) {
      this.flush();
      const timer = setTimeout(() => this.flush(), this.seconds * 1000);
      this.pending = { timer, commit, restore };
      this.message = message;
      this.visible = true;
    },

    // Confirma el borrado pendiente (si lo hay). Devuelve una promesa.
    flush() {
      const p = this.pending;
      if (!p) return Promise.resolve();
      clearTimeout(p.timer);
      this.pending = null;
      this.visible = false;
      return p.commit();
    },

    undo() {
      const p = this.pending;
      if (!p) return;
      clearTimeout(p.timer);
      this.pending = null;
      this.visible = false;
      p.restore();
    },
  });

  // Elemento borrable. Atributos: data-delete-url, data-undo-message, data-ids (opcional,
  // separados por comas) y data-after-url (opcional: adónde ir tras borrar).
  Alpine.data("deletable", () => ({
    gone: false,

    remove() {
      // $root es el elemento con x-data ($el sería el botón pulsado).
      const d = this.$root.dataset;
      const ids = (d.ids || "").split(",").filter(Boolean);
      this.gone = true;
      Alpine.store("undo").start({
        message: d.undoMessage,
        restore: () => (this.gone = false),
        commit: () =>
          hogarPost(d.deleteUrl, ids.map((id) => ["id", id])).then(() => {
            if (d.afterUrl) window.location.href = d.afterUrl;
          }),
      });
    },
  }));
});

// POST con el token CSRF (el mismo que usa HTMX, puesto en <body hx-headers>).
function hogarPost(url, pairs = []) {
  let token = "";
  try {
    token = JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRFToken"] || "";
  } catch (e) {
    /* sin token: el servidor rechazará la petición */
  }
  return fetch(url, {
    method: "POST",
    keepalive: true,
    headers: { "X-CSRFToken": token, "X-Undo-Commit": "1" },
    body: new URLSearchParams(pairs),
  }).catch(() => {});
}

// Al salir de la página, confirma el borrado pendiente.
window.addEventListener("pagehide", () => window.Alpine && Alpine.store("undo").flush());

// Antes de cualquier petición HTMX, confirma primero el borrado pendiente para que la
// respuesta no vuelva a traer el elemento borrado.
document.addEventListener("htmx:confirm", (event) => {
  const store = window.Alpine && Alpine.store("undo");
  if (!store || !store.pending) return;
  event.preventDefault();
  store.flush().finally(() => event.detail.issueRequest(true));
});

