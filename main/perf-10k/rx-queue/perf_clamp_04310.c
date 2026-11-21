/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04310(unsigned int count)
{
    const unsigned int limit = 72u;
    return count > limit ? limit : count;
}
