# Feedback email setup

The static `public/feedback.html` form is named `feedback`. It uses Netlify Forms, a honeypot, and URL-encoded submission. Name is optional; message is required. The game footer opens it in a new tab to preserve the player's unsaved route and sends only the optional name and message, plus Netlify's form identifier and spam honeypot. No city or puzzle details are attached.

To activate on the existing Netlify site:

1. In Forms, enable form detection before deploying this branch.
2. Deploy the updated public directory and confirm the `feedback` form appears in Forms.
3. Under Configuration → Notifications → Form submission notifications, add an Email notification for `feedback` with the owner's Gmail address.
4. Submit a clearly marked test from the deployed site and confirm both the Netlify submission and the received email. No Gmail password or token belongs in the repository.

Local preview deliberately does not send messages. Failed submissions preserve the message for retry. Successful submissions clear only the message; no browser storage is used. Native HTML submission remains available without JavaScript, using the dedicated thank-you page. There is no daily digest or custom email function.

Documentation: https://docs.netlify.com/manage/forms/setup/ and https://docs.netlify.com/manage/forms/notifications/
