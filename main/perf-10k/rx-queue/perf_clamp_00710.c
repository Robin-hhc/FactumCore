/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00710(unsigned int count)
{
    const unsigned int limit = 126u;
    return count > limit ? limit : count;
}
