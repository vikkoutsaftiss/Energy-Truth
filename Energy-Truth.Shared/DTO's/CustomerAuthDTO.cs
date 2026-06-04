using System;
using System.Collections.Generic;
using System.Text;

namespace Energy_Truth.Shared.DTO_s
{
    public class CustomerAuthDTO
    {
        public int Id { get; set; }
        public string Email { get; set; } = string.Empty;
        public string PasswordHash { get; set; } = string.Empty;
    }
}
