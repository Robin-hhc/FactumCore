/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06600(unsigned int count)
{
    const unsigned int limit = 158u;
    return count > limit ? limit : count;
}
