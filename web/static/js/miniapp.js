/* ==========================================================================
   КОМПОЗИТ-MES — общий слой Mini App.
   Раньше эта логика копировалась в каждый шаблон и расходилась между ними.

   Даёт:
   - подключение к Telegram WebApp (тема, разворот, кнопка «Сохранить»);
   - отправку формы с подписью initData в заголовке Authorization;
   - показ НАСТОЯЩЕЙ ошибки сервера (например «Недостаточно прав»),
     раньше пользователь всегда видел одно общее «Ошибка при сохранении».
   ========================================================================== */

const MES = (() => {
  const tg = window.Telegram?.WebApp;

  if (tg) {
    tg.ready();
    tg.expand();
  }

  /** Заголовки запроса с подписанными данными Telegram. */
  function authHeaders() {
    return {
      "Content-Type": "application/json",
      Authorization: "tma " + (tg?.initData || ""),
    };
  }

  /** Короткая вибро-отдача, если устройство её поддерживает. */
  function haptic(type) {
    try {
      tg?.HapticFeedback?.notificationOccurred(type);
    } catch (_) {
      /* не критично */
    }
  }

  /** Показать сообщение об ошибке внизу экрана. */
  function toast(text) {
    document.querySelector(".toast")?.remove();
    const el = document.createElement("div");
    el.className = "toast";
    el.setAttribute("role", "alert");
    // Иконка circle-alert из набора Lucide (lucide.dev, лицензия ISC)
    el.innerHTML =
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
      'style="flex:0 0 auto;margin-top:1px">' +
      '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>' +
      "</svg><span></span>";
    el.querySelector("span").textContent = text;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 5000);
  }

  /**
   * Вытащить понятный текст ошибки из ответа сервера.
   * FastAPI кладёт причину в поле detail (в т.ч. 403 «Недостаточно прав»).
   */
  async function errorText(resp) {
    try {
      const body = await resp.json();
      if (typeof body?.detail === "string") return body.detail;
      if (body?.detail?.needs_confirmation)
        return body.detail.warnings.join("; ");
      if (Array.isArray(body?.detail)) return "Проверьте правильность заполнения полей.";
    } catch (_) {
      /* тело не JSON — используем запасной текст ниже */
    }
    if (resp.status === 401 || resp.status === 403)
      return "Нет доступа. Откройте форму через бота под своей учётной записью.";
    if (resp.status === 404) return "Запись не найдена.";
    return `Не удалось сохранить (код ${resp.status}).`;
  }

  /** Показать экран успеха и закрыть приложение. */
  function success(message = "Сохранено") {
    haptic("success");
    const box = document.getElementById("successOverlay");
    if (box) {
      const label = box.querySelector("p");
      if (label) label.textContent = message;
      box.hidden = false;
    }
    setTimeout(() => tg?.close(), 1100);
  }

  /**
   * Подключить главную кнопку Telegram к отправке формы.
   *
   * @param {object} opts
   *   form      — id формы (для проверки полей браузером)
   *   url       — куда отправлять POST
   *   label     — надпись на кнопке
   *   collect   — функция, возвращающая объект для отправки
   *               (может вернуть null, чтобы отменить отправку)
   *   onSuccess — что показать после сохранения
   */
  function submitOn({ form, url, label = "СОХРАНИТЬ", collect, onSuccess }) {
    if (!tg) return; // открыто вне Telegram — кнопки нет

    tg.MainButton.setText(label);
    tg.MainButton.show();

    let busy = false;

    /**
     * Отправляет данные. confirmed=true означает, что работник уже
     * увидел предупреждения и согласился сохранить как есть.
     */
    async function send(payload, confirmed) {
      busy = true;
      tg.MainButton.showProgress();

      const body = confirmed ? { ...payload, confirmed: true } : payload;

      try {
        const resp = await fetch(url, {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify(body),
        });

        if (resp.ok) {
          tg.MainButton.hideProgress();
          tg.MainButton.hide();
          success(onSuccess);
          return;
        }

        tg.MainButton.hideProgress();
        busy = false;

        // 422 с needs_confirmation — это не ошибка, а вопрос: значение
        // сильно расходится с нормой либо не хватает склада. Показываем,
        // что именно смущает, и даём сохранить осознанно.
        if (resp.status === 422 && !confirmed) {
          const data = await resp.json().catch(() => null);
          if (data?.detail?.needs_confirmation) {
            haptic("warning");
            const list = data.detail.warnings.map((w) => "• " + w).join("\n");
            tg.showConfirm(
              "Проверьте данные:\n\n" + list + "\n\nВсё верно, сохранить?",
              (ok) => {
                if (ok) send(payload, true);
              }
            );
            return;
          }
          haptic("error");
          toast("Проверьте правильность заполнения полей.");
          return;
        }

        haptic("error");
        toast(await errorText(resp));
      } catch (_) {
        tg.MainButton.hideProgress();
        busy = false;
        haptic("error");
        toast("Нет связи с сервером. Проверьте интернет.");
      }
    }

    tg.MainButton.onClick(() => {
      if (busy) return; // защита от двойного нажатия и двойной записи
      const el = form ? document.getElementById(form) : null;
      if (el && !el.reportValidity()) return;

      let payload;
      try {
        payload = collect();
      } catch (e) {
        toast(e.message || "Проверьте заполнение полей.");
        haptic("error");
        return;
      }
      if (!payload) return;

      send(payload, false);
    });
  }

  /** Число из поля: пусто → null (чтобы не затирать данные нулями). */
  function num(id) {
    const raw = document.getElementById(id)?.value;
    if (raw === undefined || raw === "") return null;
    const n = parseFloat(raw);
    return Number.isFinite(n) ? n : null;
  }

  /** Строка из поля: пусто → null. */
  function str(id) {
    const raw = document.getElementById(id)?.value?.trim();
    return raw ? raw : null;
  }

  return { tg, authHeaders, toast, errorText, success, submitOn, num, str, haptic };
})();
