/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06049(unsigned int count)
{
    const unsigned int limit = 253u;
    return count > limit ? limit : count;
}
