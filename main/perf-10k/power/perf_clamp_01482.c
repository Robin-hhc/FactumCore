/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01482(unsigned int count)
{
    const unsigned int limit = 53u;
    return count > limit ? limit : count;
}
