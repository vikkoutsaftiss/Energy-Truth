using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Repositories;
using Infrastructure.DataAccess.Entities;
using Infrastructure.DataAccess.DBContext;
using Microsoft.EntityFrameworkCore;
using Energy_Truth.Shared.Login;

namespace Infrastructure.DataAccess
{
    public class CustomerRepository : ICustomerRepository
    {
        private readonly EnergyDbContext _dbContext;

        public CustomerRepository(EnergyDbContext dbContext)
        {
            _dbContext = dbContext;
        }
        public async Task<int> CreateCustomerAsync(CreateCustomerDTO customerDTO)
        {
            var newCustomer = new Customer
            {
                Email = customerDTO.Email,
                //VATNumber = customerDTO.VATNumber,
                Address = customerDTO.Address,
                Password = customerDTO.Password,
                //BusinessName = customerDTO.BusinessName,
                //CustomerType = customerDTO.CustomerType,
                //EmailConfirmed = customerDTO.EmailConfirmed
            };
            
            await _dbContext.Customers.AddAsync(newCustomer);
            await _dbContext.SaveChangesAsync();
            return newCustomer.Id;
        }

        public async Task<int> GetCustomerByEmailAsync(string email)
        {
            var customer = await _dbContext.Customers.FirstOrDefaultAsync(c => c.Email == email);
            
            if (customer != null)
            {
                return customer.Id;
            }
            return 0;
        }

        public async Task<CustomerAuthDTO?> GetCustomerAuthByEmailAsync(string email)
        {
            return await _dbContext.Customers
                .Where(c => c.Email == email)
                .Select(c => new CustomerAuthDTO
                {
                    Id = c.Id,
                    Email = c.Email,
                    PasswordHash = c.Password
                })
                .FirstOrDefaultAsync();
        }
    }
}
