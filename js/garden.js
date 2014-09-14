// Setup stuff for the page
document.captureEvents(Event.MOUSEMOVE);
document.captureEvents(Event.MOUSEDOWN);

var clickedX;
var clickedY;

document.onmousedown = function (e) {mouseClicked(e);};

function mouseClicked(e) {
  clickedX = event.clientX + document.body.scrollLeft;
  clickedY = event.clientY + document.body.scrollLeft;
  // Get the bounding box for the create_garden_form and hide it if you click
  // outside that box.
  cgf_box = document.getElementById('create_garden_form').getBoundingClientRect();
  if (((clickedX < cgf_box.left) || (clickedX > cgf_box.right)) ||
      ((clickedY < cgf_box.top) || (clickedY > cgf_box.bottom))) {
    hideCreateGarden();
  }
  return True;
}

function showCreateGarden() {
  garden_form = document.getElementById('create_garden_form');
  garden_form.style.top = clickedY;
  garden_form.style.left = clickedX;
  garden_form.style.visibility = 'visible';
  garden_form.style.zIndex = "1";
  document.getElementById('create_garden_title').focus();
}

function hideCreateGarden() {
  garden_form = document.getElementById('create_garden_form');
  garden_form.style.visibility = 'hidden';
  garden_form.style.zIndex = "-1";
}

function createGarden() {
  // validate entries
  var title = document.getElementById("garden_title");
  var year = document.getElementById("garden_year");
  var plants = document.getElementById("garden_plants");
  var messages = document.getElementById("create_garden_messages");
  var errors = new Array();
  if (title.value == '' || title.value == null) {
    errors.push('Title is Required');
    title.style.background = 'red';
  }
  if (year.value == null) {
    errors.push('A year must be selected');
    year.style.background = 'red';
  }
  var selected_plants = new Array();
  for (var x=0; x<plants.length; x++) {
    if (plants[x].selected) {
      selected_plants.push(plants[x].value);
    }
  }
  if (selected_plants.length == 0) {
    errors.push('Your garden must have plants');
    plants.style.background = 'red';
  }
  if (errors.length != 0) {
    err_msg = "<ul>";
    for (var x=0; x<errors.length; x++) {
      err_msg += '<li>' + errors[x] + '</li>';
    }
    err_msg += "</ul>Please Fix and Try Again";
    messages.style.color = '#0f0000;';
    messages.style.fontWeight = "666";
    messages.innerHTML = err_msg;
    return False;
  }

  // all good, continue making the request.
  var create_garden = new XMLHttpRequest();
  var params = "garden_title=" + title.value + "&garden_year=" + year.value;
  for (var x=0; x<selected_plants.length; x++) {
    params += "&plants=" + selected_plants[x];
  }
  create_garden.open('POST', '/mygarden/create_garden', true);
  create_garden.setRequestHeader('Content-type',
                                 'application/x-www-form-urlencoded');
  create_garden.setRequestHeader('Content-length', params.length);
  create_garden.send(params);

  messages.innerHTML = '<span class="delete_garden_interstitial">Creating Garden</span>';
  create_garden.onreadystatechange = function() {
    if (create_garden.readyState == 4 && create_garden.status == 200) {
      hideCreateGarden();
    } else {
      messages.innerHTML = '<span class="delete_garden_interstitial">' +
          create_garden.responseText + '</span>';
    }
  }
  location.reload(true);
}

function updateProfile() {
  var address = document.getElementById('profile_address').value;
  var zipcode = document.getElementById('profile_zipcode').value;
  if (zipcode == '') {
    alert('zipcode field must not be empty');
    return;
  }
  var update_request = new XMLHttpRequest();
  var params = "address=" + address + "&zipcode=" + zipcode;
  update_button = document.getElementById('update_profile_button');
  update_button.value = 'Updating User Profile';
  update_button.disabled = true;
  update_request.open('POST', '/mygarden/updateprofile', true);
  update_request.setRequestHeader("Content-type",
                                  "application/x-www-form-urlencoded");
  update_request.setRequestHeader("Content-length", params.length);
  update_request.send(params);

  update_request.onreadystatechange = function() {
    if (update_request.readyState == 4 && update_request.status == 200) {
      response = JSON.parse(update_request.responseText);
      document.getElementById('profile_city').innerHTML = response.city;
      document.getElementById('profile_state').innerHTML = response.state;
      update_button.value = 'Update Profile';
      update_button.disabled = false;
    }
  }
}

function deleteGarden(garden) {
  garden_div = document.getElementById(garden);
  garden_div.innerHTML = '<span class="delete_garden_interstitial">Deleting Garden</span>';
  var delgar_request = new XMLHttpRequest();
  delgar_request.open('GET', '/mygarden/delete?garden_title=' + encodeURIComponent(garden), true);
  delgar_request.send(null);

  delgar_request.onreadystatechange = function() {
    if (delgar_request.readyState == 4) {
      if (delgar_request.status == 200) {
        garden_div.innerHTML = '<span class="delete_garden_interstitial">Garden Deletion Complete</span>';
      } else {
        garden_div.innerHTML = '<span class="delete_garden_interstitial">Problems Deleting Garden. Please reload and try again';
      }
    }
  }
}

function deletePlants() {
  return
}

function prettyDate(date) {
    if (date == "") {
        return "&nbsp;";
    }
    var today = new Date();
    var given_dates = date.split(" to ");
    var (b_year, b_month, b_day) = given_dates[0].split('-');
    var (e_year, e_month, e_day) = given_dates[0].split('-');
    var begin = new Date();
    begin.setFullYear(int(b_year), int(b_month) - 1, int(b_day));
    var end = new Date();
    end.setFullYear(int(e_year), int(e_month) - 1, int(e_day));

    var past_due = false;
    if (today > end) {
        past_due = true;
    } else if (today < end && today > begin) {
        past_due = true;
    }

    var ret = begin.toDateString() + " to " + end.toDateString();
    if (past_due) {
        ret = "<font color='red'>" + begin.toDateString() + 
              " to " + end.toDateString() + "</font>";
    }

    document.write(ret);
}
