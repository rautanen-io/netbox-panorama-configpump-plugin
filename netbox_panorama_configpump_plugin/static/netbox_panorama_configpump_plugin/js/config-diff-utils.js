(function (global) {
    const Utils = {
        escapeHtml(text) {
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },

        debounce(fn, delay, context) {
            let timer = null;
            return (...args) => {
                if (timer) {
                    clearTimeout(timer);
                }
                timer = setTimeout(() => fn.apply(context || this, args), delay);
            };
        }
    };

    global.ConfigDiffUtils = Utils;
})(typeof window !== 'undefined' ? window : globalThis);
