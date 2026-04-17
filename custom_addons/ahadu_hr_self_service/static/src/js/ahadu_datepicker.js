(function () {
    'use strict';

    var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];
    var DAYS_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    function pad(n) { return n < 10 ? '0' + n : '' + n; }

    function parseDate(str) {
        // Parse DD/MM/YYYY
        if (!str) return null;
        var parts = str.split('/');
        if (parts.length !== 3) return null;
        var d = parseInt(parts[0], 10);
        var m = parseInt(parts[1], 10) - 1;
        var y = parseInt(parts[2], 10);
        if (isNaN(d) || isNaN(m) || isNaN(y)) return null;
        var dt = new Date(y, m, d);
        if (dt.getFullYear() !== y || dt.getMonth() !== m || dt.getDate() !== d) return null;
        return dt;
    }

    function formatDate(dt) {
        if (!dt) return '';
        return pad(dt.getDate()) + '/' + pad(dt.getMonth() + 1) + '/' + dt.getFullYear();
    }

    function buildCalendar(picker, year, month, selectedDate, todayDate) {
        var firstDay = new Date(year, month, 1).getDay();
        var daysInMonth = new Date(year, month + 1, 0).getDate();

        var rows = '';
        var day = 1;
        var total = Math.ceil((firstDay + daysInMonth) / 7);

        for (var row = 0; row < total; row++) {
            var weekNum = getWeekNumber(new Date(year, month, day > daysInMonth ? daysInMonth : day));
            rows += '<tr><td class="ahadu-dp-week">' + weekNum + '</td>';
            for (var col = 0; col < 7; col++) {
                var cellIndex = row * 7 + col;
                if (cellIndex < firstDay || day > daysInMonth) {
                    rows += '<td></td>';
                } else {
                    var isToday = (day === todayDate.getDate() && month === todayDate.getMonth() && year === todayDate.getFullYear());
                    var isSelected = selectedDate && (day === selectedDate.getDate() && month === selectedDate.getMonth() && year === selectedDate.getFullYear());
                    var cls = 'ahadu-dp-day' + (isToday ? ' ahadu-dp-today' : '') + (isSelected ? ' ahadu-dp-selected' : '');
                    rows += '<td class="' + cls + '" data-day="' + day + '">' + day + '</td>';
                    day++;
                }
            }
            rows += '</tr>';
            if (day > daysInMonth) break;
        }

        return rows;
    }

    function getWeekNumber(d) {
        var onejan = new Date(d.getFullYear(), 0, 1);
        return Math.ceil((((d - onejan) / 86400000) + onejan.getDay() + 1) / 7);
    }

    function renderPicker(picker) {
        var dp = picker._dp;
        if (!dp.mode) dp.mode = 'days';
        var year = dp.viewYear;
        var month = dp.viewMonth;
        var today = new Date();
        var selected = dp.selectedDate;

        var headerHtml =
            '<div class="ahadu-dp-header">' +
            '<button type="button" class="ahadu-dp-prev">&#8249;</button>' +
            '<span class="ahadu-dp-title" style="cursor:pointer; border-radius:4px; padding:2px 8px;">';

        var bodyHtml = '';

        if (dp.mode === 'days') {
            headerHtml += MONTHS[month] + ' ' + year + '</span>' +
                '<button type="button" class="ahadu-dp-next">&#8250;</button></div>';

            var dayHeaders = DAYS_SHORT.map(function (d) { return '<th>' + d + '</th>'; }).join('');
            bodyHtml = '<table class="ahadu-dp-table">' +
                '<thead><tr><th class="ahadu-dp-week-hd">#</th>' + dayHeaders + '</tr></thead>' +
                '<tbody>' + buildCalendar(picker, year, month, selected, today) + '</tbody>' +
                '</table>';

        } else if (dp.mode === 'months') {
            headerHtml += year + '</span>' +
                '<button type="button" class="ahadu-dp-next">&#8250;</button></div>';

            bodyHtml = '<div class="ahadu-dp-grid">';
            for (var i = 0; i < 12; i++) {
                var cls = 'ahadu-dp-grid-cell' + (i === dp.viewMonth ? ' ahadu-dp-selected' : '');
                bodyHtml += '<div class="' + cls + '" data-type="month" data-val="' + i + '">' + MONTHS[i].substring(0, 3) + '</div>';
            }
            bodyHtml += '</div>';

        } else if (dp.mode === 'years') {
            var startYear = Math.floor(year / 10) * 10;
            headerHtml += startYear + ' - ' + (startYear + 9) + '</span>' +
                '<button type="button" class="ahadu-dp-next">&#8250;</button></div>';

            bodyHtml = '<div class="ahadu-dp-grid">';
            for (var i = startYear - 1; i <= startYear + 10; i++) {
                var cls = 'ahadu-dp-grid-cell' + (i === dp.viewYear ? ' ahadu-dp-selected' : '') + (i < startYear || i > startYear + 9 ? ' text-muted' : '');
                bodyHtml += '<div class="' + cls + '" data-type="year" data-val="' + i + '">' + i + '</div>';
            }
            bodyHtml += '</div>';
        }

        dp.popup.innerHTML = headerHtml + bodyHtml;

        // Bind title click
        var titleElem = dp.popup.querySelector('.ahadu-dp-title');
        if (titleElem) {
            titleElem.addEventListener('mousedown', function (e) {
                e.preventDefault();
                if (dp.mode === 'days') dp.mode = 'months';
                else if (dp.mode === 'months') dp.mode = 'years';
                else dp.mode = 'days';
                renderPicker(picker);
            });
            titleElem.addEventListener('mouseover', function () { this.style.backgroundColor = 'rgba(255,255,255,0.2)'; });
            titleElem.addEventListener('mouseout', function () { this.style.backgroundColor = 'transparent'; });
        }

        // Bind navigation
        dp.popup.querySelector('.ahadu-dp-prev').addEventListener('mousedown', function (e) {
            e.preventDefault();
            if (dp.mode === 'days') { dp.viewMonth--; if (dp.viewMonth < 0) { dp.viewMonth = 11; dp.viewYear--; } }
            else if (dp.mode === 'months') { dp.viewYear--; }
            else if (dp.mode === 'years') { dp.viewYear -= 10; }
            renderPicker(picker);
        });
        dp.popup.querySelector('.ahadu-dp-next').addEventListener('mousedown', function (e) {
            e.preventDefault();
            if (dp.mode === 'days') { dp.viewMonth++; if (dp.viewMonth > 11) { dp.viewMonth = 0; dp.viewYear++; } }
            else if (dp.mode === 'months') { dp.viewYear++; }
            else if (dp.mode === 'years') { dp.viewYear += 10; }
            renderPicker(picker);
        });

        if (dp.mode === 'days') {
            dp.popup.querySelectorAll('.ahadu-dp-day').forEach(function (cell) {
                cell.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    var d = parseInt(this.getAttribute('data-day'), 10);
                    dp.selectedDate = new Date(year, month, d);
                    picker.value = formatDate(dp.selectedDate);
                    picker.dispatchEvent(new Event('change', { bubbles: true }));
                    hidePicker(picker);
                });
            });
        } else {
            dp.popup.querySelectorAll('.ahadu-dp-grid-cell').forEach(function (cell) {
                cell.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    var type = this.getAttribute('data-type');
                    var val = parseInt(this.getAttribute('data-val'), 10);
                    if (type === 'month') {
                        dp.viewMonth = val;
                        dp.mode = 'days';
                    } else if (type === 'year') {
                        dp.viewYear = val;
                        dp.mode = 'months';
                    }
                    renderPicker(picker);
                });
            });
        }
    }

    function showPicker(input) {
        var dp = input._dp;
        if (dp.visible) return;

        // Ensure popup is in DOM
        if (!dp.popup.parentNode) {
            document.body.appendChild(dp.popup);
        }

        // Set view to selected date or today
        var ref = dp.selectedDate || new Date();
        dp.viewYear = ref.getFullYear();
        dp.viewMonth = ref.getMonth();

        renderPicker(input);

        // Position the popup below the input
        var rect = input.getBoundingClientRect();
        var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        var scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
        dp.popup.style.top = (rect.bottom + scrollTop + 4) + 'px';
        dp.popup.style.left = (rect.left + scrollLeft) + 'px';
        dp.popup.style.display = 'block';
        dp.visible = true;
    }

    function hidePicker(input) {
        var dp = input._dp;
        dp.popup.style.display = 'none';
        dp.visible = false;
    }

    function initInput(input) {
        if (input._dp) return; // already initialized

        var popup = document.createElement('div');
        popup.className = 'ahadu-dp-popup';
        popup.style.display = 'none';
        popup.style.position = 'absolute';
        popup.style.zIndex = '99999';

        var dp = {
            popup: popup,
            visible: false,
            selectedDate: parseDate(input.value),
            viewYear: new Date().getFullYear(),
            viewMonth: new Date().getMonth()
        };
        input._dp = dp;

        input.setAttribute('autocomplete', 'off');
        input.setAttribute('placeholder', 'DD/MM/YYYY');

        input.addEventListener('focus', function () {
            dp.selectedDate = parseDate(input.value);
            showPicker(input);
        });

        input.addEventListener('input', function () {
            // Real-time parse; update selected date if valid
            var d = parseDate(input.value);
            if (d) {
                dp.selectedDate = d;
                if (dp.visible) {
                    dp.viewYear = d.getFullYear();
                    dp.viewMonth = d.getMonth();
                    renderPicker(input);
                }
            }
        });

        // Close picker when clicking outside
        document.addEventListener('mousedown', function (e) {
            if (dp.visible && e.target !== input && !dp.popup.contains(e.target)) {
                hidePicker(input);
            }
        }, true);
    }

    function initAll(scope) {
        var scope = scope || document;
        scope.querySelectorAll('.ahadu-datepicker').forEach(function (input) {
            initInput(input);
        });
    }

    // Auto-init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { initAll(); });
    } else {
        initAll();
    }

    // Expose so dynamic rows can call it
    window.ahaduDatepickerInit = initAll;
})();
