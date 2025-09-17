import json
import os
from flask import current_app, render_template, request, redirect, url_for, flash
from . import bp


@bp.route("/", methods=["GET", "POST"])
def settings_page():
    settings_path = current_app.config["SETTINGS_PATH"]
    settings = current_app.settings

    if request.method == "POST":
        model = request.form.get("model_name_or_path") or settings.get("model_name_or_path")
        threshold = float(request.form.get("threshold") or settings.get("threshold", 0.6))
        merge = int(request.form.get("merge_window_chars") or settings.get("merge_window_chars", 80))
        disclaimer = request.form.get("disclaimer") or settings.get("disclaimer", "")
        upload_max_mb = int(request.form.get("upload_max_mb") or settings.get("upload_max_mb", 15))
        enable_gemini = True if request.form.get("enable_gemini") else False
        gemini_model = request.form.get("gemini_model") or settings.get("gemini_model", "gemini-2.0-flash")

        logo_path = settings.get("logo_path", "")
        if "logo" in request.files and request.files["logo"].filename:
            logo_file = request.files["logo"]
            fname = os.path.basename(logo_file.filename)
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], f"logo_{fname}")
            logo_file.save(save_path)
            logo_path = save_path

        settings.update({
            "model_name_or_path": model,
            "threshold": threshold,
            "merge_window_chars": merge,
            "disclaimer": disclaimer,
            "upload_max_mb": upload_max_mb,
            "enable_gemini": enable_gemini,
            "gemini_model": gemini_model,
            "logo_path": logo_path,
        })
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        flash("Settings saved.", "success")
        return redirect(url_for("settings.settings_page"))

    return render_template("settings/index.html", settings=settings)

