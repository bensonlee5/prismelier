using Toybox.Application;
using Toybox.WatchUi;

class PrismelierApp extends Application.AppBase {
    var view;

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        view = new PrismelierView();
        return [view];
    }

    function onStop(state) {
        if (view != null) { view.data.stopBodyBatteryUpdates(); }
    }

    function onSettingsChanged() {
        if (view != null) {
            view.reloadSettings();
        }
        WatchUi.requestUpdate();
    }
}
