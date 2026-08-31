const supportedInfoCities = new Set(["paris", "london", "chicago", "washington-dc", "boston"]);
const requestedInfoCity = new URLSearchParams(window.location.search).get("city");
const infoCityId = supportedInfoCities.has(requestedInfoCity) ? requestedInfoCity : "paris";

document.documentElement.dataset.city = infoCityId;
document.querySelectorAll("a[data-game-link]").forEach((link) => {
  link.href = infoCityId === "paris" ? "./index.html" : `./index.html?city=${infoCityId}`;
});
document.querySelectorAll(".site-footer nav a").forEach((link) => {
  const url = new URL(link.href);
  if (infoCityId === "paris") url.searchParams.delete("city");
  else url.searchParams.set("city", infoCityId);
  link.href = url;
});
