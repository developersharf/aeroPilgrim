function initGlassSelects(root) {
    const scope = root || document;
    scope.querySelectorAll('select:not(.glass-select-native)').forEach(select => {
        if (select.dataset.glassInit) return;
        if (select.closest('.glass-select')) return;
        select.dataset.glassInit = '1';
        select.classList.add('glass-select-native');

        const wrap = document.createElement('div');
        wrap.className = 'glass-select';

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'glass-select-trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');

        const menu = document.createElement('div');
        menu.className = 'glass-select-menu';
        menu.setAttribute('role', 'listbox');

        select.parentNode.insertBefore(wrap, select);
        wrap.appendChild(select);
        wrap.appendChild(trigger);
        wrap.appendChild(menu);

        const labelSpan = document.createElement('span');
        const icon = document.createElement('i');
        icon.className = 'ph ph-caret-down';
        trigger.appendChild(labelSpan);
        trigger.appendChild(icon);

        function getLabel() {
            const opt = select.options[select.selectedIndex];
            return opt ? opt.textContent.trim() : 'Select...';
        }

        function updateSelected() {
            menu.querySelectorAll('.glass-select-option').forEach(btn => {
                btn.classList.toggle('is-selected', btn.dataset.value === select.value);
            });
            labelSpan.textContent = getLabel();
        }

        function closeMenu() {
            wrap.classList.remove('is-open');
            trigger.setAttribute('aria-expanded', 'false');
        }

        function openMenu() {
            document.querySelectorAll('.glass-select.is-open').forEach(el => {
                if (el !== wrap) {
                    el.classList.remove('is-open');
                    el.querySelector('.glass-select-trigger')?.setAttribute('aria-expanded', 'false');
                }
            });
            wrap.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
        }

        [...select.options].forEach(opt => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'glass-select-option';
            item.dataset.value = opt.value;
            item.textContent = opt.textContent.trim();
            item.setAttribute('role', 'option');
            item.addEventListener('click', () => {
                select.value = opt.value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                wrap.classList.remove('is-error');
                updateSelected();
                closeMenu();
            });
            menu.appendChild(item);
        });

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            wrap.classList.contains('is-open') ? closeMenu() : openMenu();
        });

        select.addEventListener('change', updateSelected);
        updateSelected();
    });
}

document.addEventListener('click', () => {
    document.querySelectorAll('.glass-select.is-open').forEach(el => {
        el.classList.remove('is-open');
        el.querySelector('.glass-select-trigger')?.setAttribute('aria-expanded', 'false');
    });
});

document.addEventListener('DOMContentLoaded', () => {
    initGlassSelects(document);

    document.querySelectorAll('form[data-validate-selects]').forEach(form => {
        form.addEventListener('submit', (e) => {
            let isValid = true;
            form.querySelectorAll('select').forEach(select => {
                const wrap = select.closest('.glass-select');
                if (!select.value) {
                    wrap?.classList.add('is-error');
                    isValid = false;
                } else {
                    wrap?.classList.remove('is-error');
                }
            });
            if (!isValid) {
                e.preventDefault();
                alert('Please fill in all fields');
            }
        });
    });
});
