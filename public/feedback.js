const feedbackForm = document.querySelector('#feedbackForm');
const feedbackStatus = document.querySelector('#feedbackStatus');
feedbackForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = feedbackForm.elements.namedItem('message');
  if (!message.value.trim()) {
    feedbackStatus.textContent = 'Please write a message before sending.';
    message.focus();
    return;
  }
  if (['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)) {
    feedbackStatus.textContent = 'This is a local preview. Messages can be sent once the form is live on Netlify.';
    return;
  }
  const button = feedbackForm.querySelector('button[type="submit"]');
  if (button.disabled) return;
  button.disabled = true;
  feedbackStatus.textContent = 'Sending…';
  try {
    const response = await fetch(feedbackForm.action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams(new FormData(feedbackForm)).toString(),
    });
    if (!response.ok) throw new Error('Submission failed');
    message.value = '';
    feedbackStatus.textContent = 'Thanks! Your message has been sent.';
  } catch {
    feedbackStatus.textContent = 'Your message could not be sent. Please try again, or use the GitHub link below. Your message is still here.';
  } finally {
    button.disabled = false;
  }
});
