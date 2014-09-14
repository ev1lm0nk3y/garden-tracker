<script type="text/javascript" src="//ajax.googleapis.com/ajax/libs/jquery/1.4.2/jquery.min.js"></script>
<script type="text/javascript" src="//ajax.googleapis.com/ajax/libs/jqueryui/1.8.2/jquery-ui.min.js"></script>
<script type="text/javascript" src="//ajax.googleapis.com/jsapi"></script>
<script type="text/javascript" src="//www.accountchooser.com/client.js"></script>
<script type="text/javascript">
  function load() {
        google.load("identitytoolkit", "2", {packages: ["ac"], language:"en", callback: callback});
          }
  function callback() {
        window.google.identitytoolkit.setConfig({
                  developerKey: "",
                    companyName: "Garden Tracker",
                    callbackUrl: "garden-tracker.appspot.com/signin",
                    realm: "",
                    userStatusUrl: "garden-tracker.appspot.com/mygarden",
                    loginUrl: "garden-tracker.appspot.com/login",
                    signupUrl: "garden-tracker.appspot.com/signup",
                    homeUrl: "garden-tracker.appspot.com/mygarden",
                    logoutUrl: "garden-tracker.appspot.com/logout",
                    idps: ["Gmail"],
                    tryFederatedFirst: true,
                    useContextParam: false,
                    language: "en"
                });
            window.google.identitytoolkit.init();
              }
</script>
<script type="text/javascript" src="//apis.google.com/js/client.js?onload=load"></script>

