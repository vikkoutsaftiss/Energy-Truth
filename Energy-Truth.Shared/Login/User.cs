using System;
using System.Collections.Generic;
using System.Text;
using System.Text.Json.Serialization;

namespace Energy_Truth.Shared.Login
{
    public class User
    {
        public int Id { get; private set; }
        public string Username { get; set; }
        [JsonIgnore]
        public string Password { get; set; }
        public bool IsLoggedIn { get; set; }

        public User(string username, string password)
        {
            Username = username;
            Password = password;
            IsLoggedIn = false;
        }

       
    }
}
