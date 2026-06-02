using System;
using System.Collections.Generic;
using System.Text;

namespace Energy_Truth.Shared.DTO_s
{
    public class CustomerDTO
    {
        public int Id { get; set; }
        public string Email { get; set; }
        public string Password { get; set; }
        public string Address { get; set; }
        //public string? VATNumber { get; set; }
        //public string? BusinessName { get; set; }
        //public string? CustomerType { get; set; }
        //public bool? EmailConfirmed { get; set; }
    }
}
