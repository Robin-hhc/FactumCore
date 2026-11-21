/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00482(unsigned int count)
{
    const unsigned int limit = 234u;
    return count > limit ? limit : count;
}
