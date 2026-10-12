'use strict';
(async () => {
  try {
    const response = await fetch('tasks.json');
    if (!response.ok) throw new Error('Cannot load dummy data.');
    const tasks = await response.json();
    const labels = {'first-name':'First name','last-name':'Last name','country-region':'Country/Region','birth-month':'Birthday month','birth-day':'Birthday day','birth-year':'Birthday year','email':'Email address','password':'Password','confirm-password':'Confirm password','phone-number':'Phone number'};
    const task = document.querySelector('#task');
    function render() {
      const list = document.querySelector('#values'); list.replaceChildren();
      for (const [key, value] of Object.entries(tasks[task.value])) {
        const dt = document.createElement('dt'); dt.textContent = labels[key];
        const dd = document.createElement('dd'); dd.textContent = value; list.append(dt, dd);
      }
    }
    task.addEventListener('change', render); render();
    document.querySelector('#setup').addEventListener('submit', e => {
      e.preventDefault();
      const params = new URLSearchParams({trial: document.querySelector('#trial').value, reader: document.querySelector('#reader').value, task: task.value});
      location.href = `${document.querySelector('#condition').value}/?${params}`;
    });
  } catch (error) { document.querySelector('#setup-error').textContent = error.message; }
})();
