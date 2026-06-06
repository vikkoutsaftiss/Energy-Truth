using System;
using System.Collections.Generic;
using System.Text;
using System.Text.Json.Serialization;

namespace Energy_Truth.Shared.Login
{
    public class LoggedInUser
    {
        public int Id { get; set; }
        public string Email { get; set; }
        public string Name { get; set; }
        [JsonIgnore]
        public string Password { get; set; }
        public bool IsLoggedIn { get; set; }
        public bool IsAdmin { get; set; }

        public LoggedInUser(int id, string email, string name, string password)
        {
            Id = id;
            Email = email;
            Name = name;
            Password = password;
            IsLoggedIn = false;
            IsAdmin = false;
        }

        public LoggedInUser()
        {
            
        }
    }
}
