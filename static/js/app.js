// Componentes Alpine.js de la aplicación. Se carga antes que Alpine (ambos con defer).

document.addEventListener("alpine:init", () => {
  // Selector de tema: Sistema → Claro → Oscuro. La preferencia se guarda en este navegador.
  // (En la Fase 1 se guardará también en el perfil del usuario.)
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
