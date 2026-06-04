using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Login;
using System;
using System.Collections.Generic;
using System.Text;

namespace Energy_Truth.Shared.Repositories
{
    public interface ICustomerRepository
    {
        Task<int> CreateCustomerAsync(CreateCustomerDTO customerDTO);
        Task<int> GetCustomerByEmailAsync(string email);
        Task<CustomerAuthDTO?> GetCustomerAuthByEmailAsync(string email);
    }
}
