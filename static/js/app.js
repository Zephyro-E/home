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
});
