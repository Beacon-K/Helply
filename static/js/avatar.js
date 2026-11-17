/* Shrinks the chosen picture to a 256 x 256 square (centre-cropped) before it is uploaded, so a
   phone photo of several megabytes becomes a file of a few tens of kilobytes. Falls back to
   sending the original when the browser cannot do it; the server then enforces its own limit. */
(function () {
  var input = document.querySelector("[data-avatar-input]");
  if (!input) return;
  var preview = document.querySelector("[data-avatar-preview]");
  var SIZE = 256;

  input.addEventListener("change", function () {
    var file = input.files && input.files[0];
    if (!file || !/^image\/(png|jpeg|webp)$/.test(file.type)) return;
    var url = URL.createObjectURL(file);
    var img = new Image();
    img.onload = function () {
      var side = Math.min(img.naturalWidth, img.naturalHeight);
      var canvas = document.createElement("canvas");
      canvas.width = canvas.height = SIZE;
      canvas.getContext("2d").drawImage(img, (img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2, side, side, 0, 0, SIZE, SIZE);
      URL.revokeObjectURL(url);
      canvas.toBlob(function (blob) {
        if (!blob) return;
        var small = new File([blob], "avatar.jpg", { type: "image/jpeg" });
        var list = new DataTransfer();
        list.items.add(small);
        input.files = list.files;
        if (preview) {
          preview.src = URL.createObjectURL(small);
          preview.hidden = false;
          var initials = preview.previousElementSibling;  // the letters shown while there is no photo
          if (initials && initials.tagName === "SPAN") initials.hidden = true;
        }
      }, "image/jpeg", 0.9);
    };
    img.src = url;
  });
})();
