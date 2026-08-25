const infoCityId = new URLSearchParams(window.location.search).get("city") === "london" ? "london" : "paris";

document.documentElement.dataset.city = infoCityId;
document.querySelectorAll("a[data-game-link]").forEach((link) => {
  link.href = infoCityId === "london" ? "./index.html?city=london" : "./index.html";
});
document.querySelectorAll(".site-footer nav a").forEach((link) => {
  const url = new URL(link.href);
  if (infoCityId === "london") url.searchParams.set("city", "london");
  else url.searchParams.delete("city");
  link.href = url;
});
