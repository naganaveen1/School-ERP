(function () {
  const key = 'school-erp-theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  function apply() {
    const preference = localStorage.getItem(key) || 'system';
    document.documentElement.dataset.theme = preference === 'system'
      ? (media.matches ? 'dark' : 'light') : preference;
  }
  window.schoolTheme = {
    getPreference: () => localStorage.getItem(key) || 'system',
    setPreference(value) {
      if (!['light', 'dark', 'system'].includes(value)) return;
      localStorage.setItem(key, value);
      apply();
    }
  };
  media.addEventListener('change', apply);
  apply();
})();
